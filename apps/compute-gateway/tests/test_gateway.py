"""compute-gateway tests — no live forge/graph needed (adapters injected)."""
import importlib
import os

# module-level config is read at import → set before importing server
os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo,graph-query,graph-stats"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"          # no network in tests

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, receipts, server  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    receipts._CHAINS.clear()
    # deterministic fakes for both backends
    async def fake_forge(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text=f"ran:{spec.get('code')}")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}
    async def fake_graph(spec, project, session):
        return {"outputs": [ComputeOutput(type="graph", data={"nodes": [{"id": "n1"}], "count": 1})],
                "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None}
    adapters.set_backend("forge", fake_forge)
    adapters.set_backend("hellgraph:graph-query", fake_graph)


def test_healthz():
    assert client.get("/healthz").json()["service"] == "compute-gateway"


def test_token_fail_closed():
    assert client.get("/v1/registry").status_code == 401
    assert client.post("/v1/compute", json={"kind": "notebook"}).status_code == 401


def test_contract_exposes_schemas():
    d = client.get("/v1/contract").json()
    assert "properties" in d["request"] and "properties" in d["result"]


def test_registry_shows_entitlement():
    ks = {k["kind"]: k for k in client.get("/v1/registry", params={"project": "demo"}, headers=AUTH).json()["kinds"]}
    assert ks["notebook"]["entitled"] is True          # project 'demo' entitled
    assert ks["graph-query"]["entitled"] is True        # kind entitled globally
    assert ks["spark"]["status"] == "live"                  # spark now a live backend
    assert ks["inference"]["status"] == "declared"          # adapter present, endpoint unverified


def test_notebook_routes_to_forge_with_receipt_and_warrant():
    r = client.post("/v1/compute", json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}}, headers=AUTH).json()
    assert r["status"] == "ok" and r["backend"] == "forge"
    assert r["epistemic_status"] == "derived"           # a cell is derived
    assert r["outputs"][0]["text"] == "ran:1+1"
    assert r["receipt"]["id"].startswith("sha256:") and r["receipt"]["kind"] == "notebook"
    assert r["graph_delta"]["nodes"]                    # provenance subgraph built


def test_graph_query_same_door_different_warrant():
    r = client.post("/v1/compute", json={"kind": "graph-query", "project": "demo", "spec": {"label": "demo"}}, headers=AUTH).json()
    assert r["status"] == "ok" and r["backend"] == "hellgraph"
    assert r["epistemic_status"] == "observed"          # a graph read is observed, not derived
    assert r["outputs"][0]["type"] == "graph"


def test_uniform_entitlement_gate():
    r = client.post("/v1/compute", json={"kind": "notebook", "project": "locked", "spec": {"code": "x"}}, headers=AUTH).json()
    assert r["status"] == "entitlement_required" and r["entitlement_required"] is True


def test_unknown_kind_422():
    assert client.post("/v1/compute", json={"kind": "quantum", "project": "demo"}, headers=AUTH).status_code == 422


def test_receipt_chain_and_verify():
    for code in ["a=1", "b=2", "c=3"]:
        client.post("/v1/compute", json={"kind": "notebook", "project": "demo", "spec": {"code": code}}, headers=AUTH)
    ch = client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()
    assert ch["count"] == 3
    assert ch["receipts"][1]["prev"] == ch["receipts"][0]["id"]     # chained
    assert client.get("/v1/receipts/verify", params={"project": "demo"}, headers=AUTH).json()["valid"] is True


def test_verify_detects_tamper():
    client.post("/v1/compute", json={"kind": "notebook", "project": "demo", "spec": {"code": "x"}}, headers=AUTH)
    receipts._CHAINS["demo"][0].outputs_sha = "sha256:deadbeef"     # tamper
    v = client.get("/v1/receipts/verify", params={"project": "demo"}, headers=AUTH).json()
    assert v["valid"] is False and v["broken_at"] is not None
