"""The `governance` kind: an L5 lifecycle-warden pass attested on THE estate receipt
spine (beside `materialize` — control-plane executors are proof-carrying and never grow
a parallel receipt lineage).

Covers: sealing (inputs_sha binds the run coordinates incl. the warden's own hash-chain
head), spec validation (fail loud), the provenance write-back veto (a 5-minute heartbeat
must not accrete into the knowledge graph), and memo idempotency (a warden that crashed
between sealing and recording re-seals the IDENTICAL run → the SAME receipt).
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

RUN = {
    "service": "lifecycle-warden", "run_id": "9c5f2c1e-run", "dry_run": True,
    "objects_scanned": 12, "due_count": 3, "applied_count": 0, "planned_count": 3,
    "gc_count": 1, "audit_seq": 41, "audit_head": "ab" * 32,
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
    return client.post("/v1/compute", json={"kind": "governance", "project": "demo", "spec": spec},
                       headers=AUTH).json()


def test_governance_seals_run_coordinates_on_the_chain():
    r = _compute(RUN)
    assert r["status"] == "ok" and r["kind"] == "governance" and r["backend"] == "gateway"
    assert r["epistemic_status"] == "observed"    # the gateway records the executor's report
    out = r["outputs"][0]["data"]
    assert out["service"] == "lifecycle-warden" and out["run_id"] == RUN["run_id"]
    assert out["dry_run"] is True and out["objects_scanned"] == 12
    assert out["applied_count"] == 0 and out["planned_count"] == 3 and out["gc_count"] == 1
    assert out["audit_head"] == RUN["audit_head"] and out["audit_seq"] == 41
    # the receipt landed on the project's ONE hash chain, inputs bound over the spec
    rc = r["receipt"]
    assert rc is not None and rc["inputs_sha"] == receipts.sha(RUN)
    chain = receipts.chain("demo")
    assert [c.id for c in chain] == [rc["id"]]
    assert receipts.verify("demo")["valid"] is True


def test_governance_missing_coordinates_fails_loud():
    r = _compute({"service": "lifecycle-warden", "dry_run": False})  # no run_id, no audit head
    assert r["status"] == "error"
    assert "run_id" in r["error"] and "audit_head" in r["error"]


def test_governance_never_writes_provenance_back_into_the_graph():
    engine.WRITE_PROVENANCE = True
    calls = []

    async def recording_write(delta):
        calls.append(delta)
        return True

    adapters.write_provenance = recording_write

    r = _compute(RUN)
    assert r["status"] == "ok"
    assert calls == []                            # the veto held: no heartbeat accretion
    assert r["graph_delta"]["written"] is False


def test_governance_retry_returns_the_same_receipt():
    first = _compute(RUN)
    again = _compute(RUN)
    assert again["memoized"] is True
    assert again["receipt"]["id"] == first["receipt"]["id"]
    assert len(receipts.chain("demo")) == 1
