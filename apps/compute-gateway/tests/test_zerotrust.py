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

from compute_gateway import adapters, engine, grants, receipts, registry, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo,graph-query,graph-stats,spark"   # pin: shared env
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    grants._reset()
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


def test_enforce_permits_with_real_grant():
    # the full deep flow: request a grant (notebook is HIGH → needs a human quorum
    # signature), then present it on /v1/compute under enforce.
    gr = client.post("/v1/grants", json={"kind": "notebook", "project": "demo",
                     "quorum_signatures": [{"spiffe_id": "spiffe://x/human", "sig": "0" * 16}]},
                     headers=AUTH).json()
    gid = gr["grant"]["grant_id"]
    zerotrust.ZEROTRUST_ENFORCE = True
    r = client.post("/v1/compute",
                    json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"},
                          "grant_id": gid}, headers=AUTH).json()
    assert r["status"] == "ok" and r["grant_check"]["result"]["valid"] is True


def test_enforce_denies_unknown_and_revoked_grant():
    zerotrust.ZEROTRUST_ENFORCE = True
    # an unknown grant fails closed
    r = client.post("/v1/compute", json={"kind": "notebook", "project": "demo",
                    "spec": {"code": "x"}, "grant_id": "grant-does-not-exist"}, headers=AUTH).json()
    assert r["status"] == "grant_required" and r["grant_check"]["result"]["reason"] == "unknown grant"
    # a revoked grant fails closed too
    zerotrust.ZEROTRUST_ENFORCE = False
    gr = client.post("/v1/grants", json={"kind": "graph-query", "project": "demo"}, headers=AUTH).json()
    gid = gr["grant"]["grant_id"]
    client.post(f"/v1/grants/{gid}/revoke", headers=AUTH)
    zerotrust.ZEROTRUST_ENFORCE = True
    r2 = client.post("/v1/compute", json={"kind": "graph-query", "project": "demo",
                     "spec": {"label": "demo"}, "grant_id": gid}, headers=AUTH).json()
    assert r2["status"] == "grant_required" and r2["grant_check"]["result"]["revoked"] is True


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


# ── ZEROTRUST_ENFORCE: the flag must MEAN what the estate spells ──
# Regression: the flag was `os.getenv(...).lower() == "true"`, so ZEROTRUST_ENFORCE=1 — the
# estate's dominant spelling (NOETICA_SHACL_ENFORCE, BROKER_REQUIRE_KEY, SERVICE_REGISTER_STRICT,
# PREMERGE_STRICT) — parsed as False and the gate was silently OFF. With it off, grant_check()
# validates nothing against the store: a revoked grant returns valid=True on entitlement alone.

def _reimport_with(value: str | None):
    """Re-import zerotrust with ZEROTRUST_ENFORCE set (or unset) — it is read at import."""
    prev = os.environ.get("ZEROTRUST_ENFORCE")
    if value is None:
        os.environ.pop("ZEROTRUST_ENFORCE", None)
    else:
        os.environ["ZEROTRUST_ENFORCE"] = value
    try:
        return importlib.reload(zerotrust).ZEROTRUST_ENFORCE
    finally:
        if prev is None:
            os.environ.pop("ZEROTRUST_ENFORCE", None)
        else:
            os.environ["ZEROTRUST_ENFORCE"] = prev
        importlib.reload(zerotrust)
        zerotrust.ZEROTRUST_ENFORCE = False


def test_enforce_flag_accepts_the_conventional_truthy_set():
    for spelling in ("1", "true", "TRUE", "True", "yes", "YES", "on", "ON", " true ", " 1 "):
        assert _reimport_with(spelling) is True, f"{spelling!r} must enable enforcement"
    for spelling in ("0", "false", "no", "off", "", "  ", "maybe"):
        assert _reimport_with(spelling) is False, f"{spelling!r} must NOT enable enforcement"
    assert _reimport_with(None) is False, "absent stays off — the default is not being flipped here"


def test_enforce_via_numeric_one_actually_refuses_a_revoked_grant():
    """The whole point: `=1` must not just parse True, it must reach the enforcement block."""
    gr = client.post("/v1/grants", json={"kind": "graph-query", "project": "demo"},
                     headers=AUTH).json()
    gid = gr["grant"]["grant_id"]
    client.post(f"/v1/grants/{gid}/revoke", headers=AUTH)

    prev = os.environ.get("ZEROTRUST_ENFORCE")
    os.environ["ZEROTRUST_ENFORCE"] = "1"
    try:
        importlib.reload(zerotrust)
        assert zerotrust.ZEROTRUST_ENFORCE is True
        check, permitted = zerotrust.grant_check(project="demo", kind="graph-query",
                                                 backend="hellgraph", actor="a",
                                                 grant_id=gid, entitled=True)
        assert permitted is False, "a revoked grant must be refused when ZEROTRUST_ENFORCE=1"
        assert check["result"]["revoked"] is True
        assert check["result"]["valid"] is False

        # ...and a VALID grant still passes: this is a gate, not a wall.
        ok = client.post("/v1/grants", json={"kind": "graph-query", "project": "demo"},
                         headers=AUTH).json()["grant"]["grant_id"]
        _c2, permitted2 = zerotrust.grant_check(project="demo", kind="graph-query",
                                                backend="hellgraph", actor="a",
                                                grant_id=ok, entitled=True)
        assert permitted2 is True, "a live grant must still be admitted"
    finally:
        if prev is None:
            os.environ.pop("ZEROTRUST_ENFORCE", None)
        else:
            os.environ["ZEROTRUST_ENFORCE"] = prev
        importlib.reload(zerotrust)
        zerotrust.ZEROTRUST_ENFORCE = False


def test_disabled_enforcement_leaks_a_revoked_grant_and_says_so_out_loud():
    """Pin BOTH halves of the silent-wrong: the leak is real, and it is now announced."""
    gr = client.post("/v1/grants", json={"kind": "graph-query", "project": "demo"},
                     headers=AUTH).json()
    gid = gr["grant"]["grant_id"]
    client.post(f"/v1/grants/{gid}/revoke", headers=AUTH)

    zerotrust.ZEROTRUST_ENFORCE = False
    _check, permitted = zerotrust.grant_check(project="demo", kind="graph-query",
                                              backend="hellgraph", actor="a",
                                              grant_id=gid, entitled=True)
    assert permitted is True, "documents the cost of off: a revoked grant passes on entitlement"

    said: list[str] = []
    assert zerotrust.warn_if_unenforced(said.append) is True
    assert len(said) == 1, "exactly one WARN (auth.ts / membrane.ts discipline)"
    msg = said[0]
    assert "ZEROTRUST_ENFORCE" in msg and "OFF" in msg
    assert "REVOKED" in msg, "the warning must name what it costs, not just that a flag is off"

    zerotrust.ZEROTRUST_ENFORCE = True
    said2: list[str] = []
    assert zerotrust.warn_if_unenforced(said2.append) is False
    assert said2 == [], "enforced startup is quiet"
    zerotrust.ZEROTRUST_ENFORCE = False


def test_env_flag_helper_is_the_one_convention():
    prev = os.environ.get("_ZT_PROBE")
    try:
        for v, want in (("1", True), ("true", True), ("yes", True), ("on", True),
                        ("ON", True), (" 1 ", True), ("0", False), ("off", False),
                        ("", False), ("nope", False)):
            os.environ["_ZT_PROBE"] = v
            assert zerotrust.env_flag("_ZT_PROBE") is want, f"{v!r}"
        os.environ.pop("_ZT_PROBE", None)
        assert zerotrust.env_flag("_ZT_PROBE") is False
        assert zerotrust.env_flag("_ZT_PROBE", "on") is True, "callers may default to on"
    finally:
        if prev is None:
            os.environ.pop("_ZT_PROBE", None)
        else:
            os.environ["_ZT_PROBE"] = prev
