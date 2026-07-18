"""The `workflow` composite kind — a DAG of governed sub-computes bound by one
composite receipt. Every step is itself gated, memoized, and receipt-sealed."""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"          # project 'demo' → all kinds entitled
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, engine, receipts, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    zerotrust.ZEROTRUST_ENFORCE = False

    async def fake_forge(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text=f"ran:{spec.get('code')}")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}

    async def fake_graph(spec, project, session):
        return {"outputs": [ComputeOutput(type="graph", data={"nodes": [], "count": 0})],
                "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None}

    adapters.set_backend("forge", fake_forge)
    adapters.set_backend("hellgraph:graph-query", fake_graph)


def _wf(steps, project="demo", **extra):
    return client.post("/v1/compute",
                       json={"kind": "workflow", "project": project, "spec": {"steps": steps}, **extra},
                       headers=AUTH).json()


def test_workflow_runs_dag_and_seals_composite_receipt():
    r = _wf([
        {"id": "read", "kind": "graph-query", "spec": {"label": "demo"}},
        {"id": "cell", "kind": "notebook", "spec": {"code": "1+1"}, "needs": ["read"]},
    ])
    assert r["status"] == "ok" and r["kind"] == "workflow" and r["backend"] == "gateway"
    steps = r["outputs"][0]["data"]["steps"]
    assert [s["id"] for s in steps] == ["read", "cell"]       # topological order honoured
    assert all(s["receipt"] for s in steps)                    # each step sealed its own receipt
    # composite receipt + two step receipts all landed in the chain
    assert client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()["count"] == 3
    assert r["receipt"]["kind"] == "workflow"


def test_workflow_warrant_is_weakest_link():
    # graph-query is 'observed', notebook is 'derived'. weakest(observed, derived) = observed.
    r = _wf([
        {"id": "read", "kind": "graph-query", "spec": {"label": "demo"}},
        {"id": "cell", "kind": "notebook", "spec": {"code": "x"}},
    ])
    assert r["epistemic_status"] == "observed"
    assert r["outputs"][0]["data"]["warrant"] == "observed"


def test_workflow_provenance_links_steps():
    r = _wf([{"id": "a", "kind": "notebook", "spec": {"code": "1"}},
             {"id": "b", "kind": "notebook", "spec": {"code": "2"}, "needs": ["a"]}])
    labels = [e["label"] for e in r["graph_delta"]["edges"]]
    assert "HAS_STEP" in labels and "prov:wasInformedBy" in labels


def test_workflow_fail_fast_stops_dependents():
    async def boom(spec, project, session):
        return {"outputs": [], "runtime": "python3", "status": "error",
                "error": "kaboom", "degraded": None}
    adapters.set_backend("forge", boom)
    r = _wf([
        {"id": "bad", "kind": "notebook", "spec": {"code": "x"}},
        {"id": "never", "kind": "notebook", "spec": {"code": "y"}, "needs": ["bad"]},
    ])
    assert r["status"] == "error"
    ran = [s["id"] for s in r["outputs"][0]["data"]["steps"]]
    assert ran == ["bad"] and "never" not in ran               # dependent skipped


def test_workflow_rejects_cycle():
    r = _wf([{"id": "a", "kind": "notebook", "spec": {}, "needs": ["b"]},
             {"id": "b", "kind": "notebook", "spec": {}, "needs": ["a"]}])
    assert r["status"] == "error" and "cycle" in (r["error"] or "")


def test_workflow_rejects_unknown_dependency():
    r = _wf([{"id": "a", "kind": "notebook", "spec": {}, "needs": ["ghost"]}])
    assert r["status"] == "error" and "unknown step" in (r["error"] or "")


def test_workflow_memoized_end_to_end():
    steps = [{"id": "a", "kind": "notebook", "spec": {"code": "1+1"}}]
    r1 = _wf(steps)
    r2 = _wf(steps)
    assert r1["memoized"] is False and r2["memoized"] is True
    assert r1["receipt"]["id"] == r2["receipt"]["id"]


def test_workflow_in_registry_and_capability():
    ks = {k["kind"]: k for k in client.get("/v1/registry", params={"project": "demo"}, headers=AUTH).json()["kinds"]}
    assert ks["workflow"]["status"] == "live" and ks["workflow"]["backends"] == ["gateway"]
    reg = client.get("/v1/capability-registry", headers=AUTH).json()
    zerotrust.validate(reg, "capability_registry")
    assert any(t["name"] == "compute.workflow" for t in reg["servers"][0]["tools"])
