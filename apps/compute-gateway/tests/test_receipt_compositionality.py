"""D5 (Metaphor→Mechanism W6.0) — the ONE enforced effect-algebra law.

The design's monad stack ships not as a library but as a property the gateway must
uphold forever: a workflow's composite receipt IS the fold of its step receipts.
Concretely, four sub-laws over a real orchestrated run:

  1. WARRANT FOLD (monoid on the epistemic lattice): composite.epistemic_status
     == weakest(step statuses). No step can be laundered upward by composition.
  2. STRUCTURAL FOLD: the composite's outputs embed exactly the sealed step
     receipt ids, in DAG order — the composite references its parts, all of them,
     and nothing else.
  3. BINDING: composite.outputs_sha recomputes from the composite outputs (which
     embed the step ids) and composite.inputs_sha from the workflow spec — so the
     fold is hash-bound, not just asserted. (verify() checks the id-hash; this
     checks the CONTENT hashes it covers.)
  4. DETERMINISM: an identical workflow folds to the IDENTICAL composite receipt
     (memo law) — composition is a function, not an event.

If any of these breaks, composition is no longer lawful and the register entry
`effect-discipline` goes red. See docs/METAPHOR_TO_MECHANISM_PROGRAM.md.
"""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, engine, receipts, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}

WF = {"kind": "workflow", "project": "demo", "spec": {"steps": [
    {"id": "read",  "kind": "graph-query", "spec": {"label": "demo"}},
    {"id": "cell",  "kind": "notebook",    "spec": {"code": "1+1"}, "needs": ["read"]},
    {"id": "cell2", "kind": "notebook",    "spec": {"code": "2+2"}, "needs": ["cell"]},
]}}


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
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


def _run_wf():
    return client.post("/v1/compute", json=WF, headers=AUTH).json()


def test_law1_warrant_is_the_weakest_link_fold():
    r = _run_wf()
    steps = r["outputs"][0]["data"]["steps"]
    order = ["unknown", "hypothesis", "simulated", "observed", "derived", "verified", "attested"]
    folded = min((s["epistemic_status"] for s in steps), key=order.index)
    assert r["epistemic_status"] == folded            # composite == fold(min) over the lattice
    assert r["receipt"]["epistemic_status"] == folded  # and the SEALED receipt agrees


def test_law2_composite_embeds_exactly_its_step_receipts_in_dag_order():
    r = _run_wf()
    embedded = [s["receipt"] for s in r["outputs"][0]["data"]["steps"]]
    assert all(embedded), "every step must seal a receipt"
    chain = client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()["receipts"]
    chain_ids = [c["id"] for c in chain]
    # exactly the steps + the composite, nothing else, and steps in chain (=execution) order
    assert chain_ids[:-1] == embedded
    assert chain_ids[-1] == r["receipt"]["id"]
    # DAG order respected (read -> cell -> cell2 per `needs`)
    kinds = [s["id"] for s in r["outputs"][0]["data"]["steps"]]
    assert kinds == ["read", "cell", "cell2"]


def test_law3_fold_is_hash_bound():
    r = _run_wf()
    # outputs_sha binds the outputs that EMBED the step ids — recompute and compare
    assert r["receipt"]["outputs_sha"] == receipts.sha(r["outputs"])
    # inputs_sha binds the workflow spec that DECLARED the steps
    assert r["receipt"]["inputs_sha"] == receipts.sha(WF["spec"])
    # and the chain as a whole still verifies (id-hash + prev-links + signatures)
    v = client.get("/v1/receipts/verify", params={"project": "demo"}, headers=AUTH).json()
    assert v["valid"] and v["count"] == 4


def test_law4_composition_is_deterministic():
    r1 = _run_wf()
    r2 = _run_wf()
    assert r2["memoized"] is True
    assert r1["receipt"]["id"] == r2["receipt"]["id"]   # same fold -> same composite, always
