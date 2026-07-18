"""Zero-trust conformance, signed attestation, memoization, and spark routing.

These lock the gateway's integration with OUR authority kernel
(SocioProphet/mcp-a2a-zero-trust): every payload we emit is validated against the
VENDORED kernel schema, so a drift in either side fails the build.
"""
import base64
import importlib
import os

# module-level config is read at import → set before importing server.
os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo,graph-query,graph-stats,spark"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"
# a deterministic Ed25519 seed so receipts are SIGNED in-test (32 bytes b64).
os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"0" * 32).decode()

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, receipts, registry, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    receipts._CHAINS.clear()
    server._MEMO.clear()
    zerotrust.ZEROTRUST_ENFORCE = False

    async def fake_forge(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text=f"ran:{spec.get('code')}")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}

    async def fake_spark(spec, project, session):
        return {"outputs": [ComputeOutput(type="table", data={"rows": [{"n": 1}], "row_count": 1})],
                "runtime": "spark", "status": "ok", "error": None, "degraded": None}

    adapters.set_backend("forge", fake_forge)
    adapters.set_backend("spark-runner", fake_spark)


# ── capability registry ──
def test_capability_registry_conforms_to_kernel_schema():
    reg = client.get("/v1/capability-registry", headers=AUTH).json()
    zerotrust.validate(reg, "capability_registry")           # vendored kernel schema
    srv = reg["servers"][0]
    assert srv["name"] == "compute-gateway" and srv["side"] in ("edge", "twin", "either")
    tools = {t["name"]: t for t in srv["tools"]}
    assert tools["compute.notebook"]["effect"] == "exec"      # user code
    assert tools["compute.graph_query"]["effect"] == "read"   # graph read
    assert tools["compute.notebook"]["danger_class_hint"] == "HIGH"
    assert all(t["capability_digest"].startswith("sha256:") for t in srv["tools"])


# ── ToolGrantCheck on every compute ──
def test_compute_emits_conforming_grant_check():
    r = client.post("/v1/compute",
                    json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"},
                          "grant_id": "grant-abc12345"}, headers=AUTH).json()
    assert r["status"] == "ok"
    zerotrust.validate(r["grant_check"], "tool_grant_check")
    assert r["grant_check"]["result"]["valid"] is True
    assert r["grant_check"]["operation"] == "tool_grant.validate"
    assert r["grant_check"]["policy_hash"].startswith("sha256:")


def test_grant_check_present_on_entitlement_denial():
    r = client.post("/v1/compute",
                    json={"kind": "notebook", "project": "locked", "spec": {"code": "x"}},
                    headers=AUTH).json()
    assert r["status"] == "entitlement_required"
    zerotrust.validate(r["grant_check"], "tool_grant_check")
    assert r["grant_check"]["result"]["valid"] is False


def test_zerotrust_enforce_fails_closed_without_grant():
    zerotrust.ZEROTRUST_ENFORCE = True
    r = client.post("/v1/compute",
                    json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}},
                    headers=AUTH).json()
    assert r["status"] == "grant_required"               # entitled but no capability grant
    assert r["grant_check"]["result"]["valid"] is False
    # a graph READ (no user code) is NOT forced to carry a grant
    r2 = client.post("/v1/compute",
                     json={"kind": "graph-query", "project": "demo", "spec": {"label": "demo"}},
                     headers=AUTH)
    assert r2.json()["status"] in ("ok", "degraded")     # not grant_required


def test_enforce_permits_with_grant():
    zerotrust.ZEROTRUST_ENFORCE = True
    r = client.post("/v1/compute",
                    json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"},
                          "grant_id": "grant-xyz98765"}, headers=AUTH).json()
    assert r["status"] == "ok" and r["grant_check"]["result"]["valid"] is True


# ── AttestationBundle over the signed receipt ──
def test_attestation_bundle_conforms_and_is_cosign_valid():
    r = client.post("/v1/compute",
                    json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}},
                    headers=AUTH).json()
    att = r["attestation"]
    zerotrust.validate(att, "attestation_bundle")
    assert att["results"]["cosign_valid"] is True        # Ed25519 sig verifies
    assert att["results"]["tpm_valid"] is False          # no hardware root (honest)
    assert att["subject"]["aum_digest"] == r["receipt"]["id"]


def test_attestation_endpoint_and_signed_verify():
    client.post("/v1/compute",
                json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}}, headers=AUTH)
    att = client.get("/v1/attestation", params={"project": "demo"}, headers=AUTH).json()
    assert att["count"] == 1
    zerotrust.validate(att["attestations"][0], "attestation_bundle")
    v = client.get("/v1/receipts/verify", params={"project": "demo"}, headers=AUTH).json()
    assert v["valid"] is True and v["signed"] == 1        # the receipt carried a verifying sig


# ── content-addressed memoization ──
def test_memoization_returns_identical_proof():
    body = {"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}}
    r1 = client.post("/v1/compute", json=body, headers=AUTH).json()
    r2 = client.post("/v1/compute", json=body, headers=AUTH).json()
    assert r1["memoized"] is False and r2["memoized"] is True
    assert r1["receipt"]["id"] == r2["receipt"]["id"]     # same sealed proof
    # only ONE receipt actually sealed into the chain
    assert client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()["count"] == 1


def test_no_cache_bypasses_memo():
    body = {"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}, "no_cache": True}
    client.post("/v1/compute", json=body, headers=AUTH)
    r2 = client.post("/v1/compute", json=body, headers=AUTH).json()
    assert r2["memoized"] is False
    assert client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()["count"] == 2


# ── spark: the Databricks paradigm as one backend behind the uniform door ──
def test_spark_routes_live_with_receipt_and_warrant():
    assert registry.KINDS["spark"]["status"] == "live"
    r = client.post("/v1/compute",
                    json={"kind": "spark", "project": "demo", "spec": {"sql": "select 1 n"}},
                    headers=AUTH).json()
    assert r["status"] == "ok" and r["backend"] == "spark-runner"
    assert r["epistemic_status"] == "derived"
    assert r["outputs"][0]["type"] == "table"
    assert r["receipt"]["kind"] == "spark"               # same universal receipt
