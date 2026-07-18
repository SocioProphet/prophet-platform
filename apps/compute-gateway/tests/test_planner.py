"""The planner — the capability registry as an agent action space (layer 6).

A plan is a preview (free, ungated); the emitted workflow spec runs under full
governance through /v1/compute. These lock the plan→execute round-trip."""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"          # only project 'demo' entitled
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
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"       # pin: sibling test modules widen the shared env

    async def fake_forge(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text="ok")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}

    async def fake_stats(spec, project, session):
        return {"outputs": [ComputeOutput(type="table", data={"n": 1})],
                "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None}

    adapters.set_backend("forge", fake_forge)
    adapters.set_backend("hellgraph:graph-stats", fake_stats)


def _plan(caps, project="demo", **extra):
    return client.post("/v1/plan", json={"capabilities": caps, "project": project, **extra},
                       headers=AUTH).json()


def test_plan_composes_read_then_derive_dag():
    p = _plan(["counts", "python"], intent="profile the cohort")
    assert p["strategy"] == "capability-dag" and p["intent"] == "profile the cohort"
    steps = p["plan"]["spec"]["steps"]
    kinds = [s["kind"] for s in steps]
    assert kinds == ["graph-stats", "notebook"]           # observed read first, then derive
    # the derive fans in on the read
    derive = next(s for s in steps if s["kind"] == "notebook")
    assert derive["needs"] == ["read-1-graph-stats"]
    assert p["warrant_preview"] == "observed"             # weakest link
    assert p["runnable"] is True and not p["unmet_capabilities"]


def test_plan_output_is_a_runnable_workflow():
    p = _plan(["counts", "python"])
    # hand the plan straight to /v1/compute — the round-trip the layer promises
    r = client.post("/v1/compute", json=p["plan"], headers=AUTH).json()
    assert r["status"] == "ok" and r["kind"] == "workflow"
    ran = [s["id"] for s in r["outputs"][0]["data"]["steps"]]
    assert ran == ["read-1-graph-stats", "derive-1-notebook"]


def test_plan_reports_unmet_capability():
    p = _plan(["counts", "teleportation"])
    assert p["unmet_capabilities"] == ["teleportation"]
    assert p["runnable"] is False                          # can't satisfy the goal


def test_planning_is_free_but_flags_unentitled():
    # project 'locked' is NOT entitled — planning still returns 200 (free preview),
    # but every step is flagged unentitled and the plan is not runnable.
    p = _plan(["counts"], project="locked")
    assert p["steps"][0]["entitled"] is False
    assert p["unmet_entitlements"] and p["runnable"] is False


def test_plan_dedupes_kinds_across_capabilities():
    # both 'counts' and 'analytics' are provided by graph-stats → one step, not two
    p = _plan(["counts", "analytics"])
    assert [s["kind"] for s in p["plan"]["spec"]["steps"]] == ["graph-stats"]


def test_plan_requires_auth():
    assert client.post("/v1/plan", json={"capabilities": ["counts"]}).status_code == 401
