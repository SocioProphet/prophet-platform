"""Seal-the-Walls W1.1 — the `materialize` kind: a materializer batch attested on THE
estate receipt spine (pht.md Design commitment 3: materializers are proof-carrying and
NEVER grow a parallel receipt lineage).

Covers: sealing (inputs_sha binds the batch coordinates), spec validation (fail loud),
the provenance write-back veto (a materialize receipt must not feed the very log being
materialized), and memo idempotency (a retried batch returns the SAME receipt).
"""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, engine, receipts, server  # noqa: E402

importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}

BATCH = {
    "source": "hellgraph", "sink": "clickhouse", "table": "hellgraph.events",
    "from_cursor": 100, "to_cursor": 158, "row_count": 42,
    "batch_hash": "sha256:" + "ab" * 32,
}

_ORIG_WRITE_PROVENANCE_FLAG = engine.WRITE_PROVENANCE
_ORIG_WRITE_PROVENANCE_FN = adapters.write_provenance


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"   # pin: sibling modules mutate the shared env
    receipts._CHAINS.clear()
    engine._MEMO.clear()


def teardown_function():
    engine.WRITE_PROVENANCE = _ORIG_WRITE_PROVENANCE_FLAG
    adapters.write_provenance = _ORIG_WRITE_PROVENANCE_FN


def _compute(spec):
    return client.post("/v1/compute", json={"kind": "materialize", "project": "demo", "spec": spec},
                       headers=AUTH).json()


def test_materialize_seals_batch_coordinates_on_the_chain():
    r = _compute(BATCH)
    assert r["status"] == "ok" and r["kind"] == "materialize" and r["backend"] == "gateway"
    assert r["epistemic_status"] == "derived"                     # a materialized view is derived
    out = r["outputs"][0]["data"]
    assert out["from_cursor"] == 100 and out["to_cursor"] == 158
    assert out["row_count"] == 42 and out["batch_hash"] == BATCH["batch_hash"]
    # the receipt landed on the project's ONE hash chain, inputs bound over the spec
    rc = r["receipt"]
    assert rc is not None and rc["inputs_sha"] == receipts.sha(BATCH)
    chain = receipts.chain("demo")
    assert [c.id for c in chain] == [rc["id"]]
    assert receipts.verify("demo")["valid"] is True


def test_materialize_missing_coordinates_fails_loud():
    r = _compute({"sink": "clickhouse", "table": "hellgraph.events"})  # no cut, no hash
    assert r["status"] == "error"
    assert "to_cursor" in r["error"] and "batch_hash" in r["error"]


def test_materialize_never_writes_provenance_back_into_the_log():
    # force the provenance path ON, and record any write-back attempt
    engine.WRITE_PROVENANCE = True
    calls = []

    async def recording_write(delta):
        calls.append(delta)
        return True

    adapters.write_provenance = recording_write

    r = _compute(BATCH)
    assert r["status"] == "ok"
    assert calls == []                                            # the veto held: no graph write-back
    assert r["graph_delta"]["written"] is False

    # control: a non-materialize kind DOES write provenance under the same flag,
    # proving the veto is per-adapter, not a dead code path.
    async def fake_graph(spec, project, session):
        from compute_gateway.contract import ComputeOutput
        return {"outputs": [ComputeOutput(type="graph", data={"count": 1})],
                "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None}

    orig = adapters._BACKENDS["hellgraph:graph-stats"]
    adapters.set_backend("hellgraph:graph-stats", fake_graph)
    try:
        os.environ["COMPUTE_ENTITLEMENTS"] = "demo,graph-stats"
        c = client.post("/v1/compute", json={"kind": "graph-stats", "project": "demo", "spec": {}},
                        headers=AUTH).json()
        assert c["status"] == "ok" and len(calls) == 1
    finally:
        adapters.set_backend("hellgraph:graph-stats", orig)


def test_materialize_retry_returns_the_same_receipt():
    # a materializer that crashed after sealing but before checkpointing re-runs the
    # IDENTICAL batch → the memo returns the same receipt, not a duplicate on the chain
    first = _compute(BATCH)
    again = _compute(BATCH)
    assert again["memoized"] is True
    assert again["receipt"]["id"] == first["receipt"]["id"]
    assert len(receipts.chain("demo")) == 1
