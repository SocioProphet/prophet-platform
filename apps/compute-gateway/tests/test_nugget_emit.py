"""Seal-the-Walls W6.2 — the `nugget-emit` kind: one document's KnowledgeNugget emission
attested on THE estate receipt spine (never a parallel receipt lineage — the extraction
spine seals through the same door the materializer and the lifecycle warden use).

Covers: sealing (inputs_sha binds the batch coordinates INCLUDING the rejected count),
the two refusals that keep warrant status un-fudgeable (a warrant outside the closed v0.1
taxonomy; counts that do not sum), the provenance write-back veto, and memo idempotency.
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
    "doc_ref": "urn:srcos:dataset:gyg_asx_fy2025_annual_report",
    "content_hash": "sha256-" + "0d" * 32,
    "raw_sha256": "ab" * 32,
    "media_type": "application/pdf",
    "nugget_count": 7,
    "warrant_counts": {"direct-quote": 4, "computed": 2, "model-generated": 1},
    "validation_failures": 0,
    "batch_hash": "cd" * 32,
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
    return client.post("/v1/compute",
                       json={"kind": "nugget-emit", "project": "demo", "spec": spec},
                       headers=AUTH).json()


def test_nugget_emit_seals_the_batch_coordinates_on_the_chain():
    r = _compute(BATCH)
    assert r["status"] == "ok" and r["kind"] == "nugget-emit" and r["backend"] == "gateway"
    assert r["epistemic_status"] == "observed"
    out = r["outputs"][0]["data"]
    assert out["doc_ref"] == BATCH["doc_ref"]
    assert out["content_hash"] == BATCH["content_hash"]
    assert out["nugget_count"] == 7 and out["batch_hash"] == BATCH["batch_hash"]
    # every warrant kind is present in the sealed counts, zeros included — the shape of
    # the attested composition does not change with the document.
    assert out["warrant_counts"] == {"direct-quote": 4, "computed": 2, "inferred": 0,
                                     "model-generated": 1}
    # the admissibility-relevant split is computed once, here, and sealed
    assert out["model_generated_count"] == 1
    rc = r["receipt"]
    assert rc is not None and rc["inputs_sha"] == receipts.sha(BATCH)
    assert [c.id for c in receipts.chain("demo")] == [rc["id"]]
    assert receipts.verify("demo")["valid"] is True


def test_the_rejected_count_is_sealed_not_only_reported():
    """A silent collapse in extraction quality must be visible on the chain, not only in
    the producer's /healthz gauge."""
    spec = {**BATCH, "validation_failures": 3}
    r = _compute(spec)
    assert r["outputs"][0]["data"]["validation_failures"] == 3
    assert r["receipt"]["inputs_sha"] != receipts.sha(BATCH)   # it is bound into inputs


def test_missing_coordinates_fail_loud():
    r = _compute({"doc_ref": "urn:srcos:dataset:x"})
    assert r["status"] == "error"
    assert "content_hash" in r["error"] and "batch_hash" in r["error"]


def test_a_warrant_outside_the_closed_taxonomy_is_refused():
    """The v0.1 warrant taxonomy is closed. Sealing an unrecognised warrant would put a
    receipt behind content that downstream admissibility weighting cannot type."""
    r = _compute({**BATCH, "nugget_count": 8,
                  "warrant_counts": {**BATCH["warrant_counts"], "hearsay": 1}})
    assert r["status"] == "error"
    assert "hearsay" in r["error"] and "closed v0.1 taxonomy" in r["error"]


def test_counts_that_do_not_add_up_are_refused():
    """It is exactly the model-generated share a miscount would hide."""
    r = _compute({**BATCH, "nugget_count": 99})
    assert r["status"] == "error" and "does not add up" in r["error"]


def test_nugget_emit_never_writes_provenance_back_into_the_graph():
    # the nuggets, their document, their KKO type nodes and their warrantedBy edges are
    # ALREADY in hellgraph — written by the producer. A write-back would be a second,
    # weaker copy of the same lineage, minted on every document, forever.
    engine.WRITE_PROVENANCE = True
    calls = []

    async def recording_write(delta):
        calls.append(delta)
        return True

    adapters.write_provenance = recording_write
    r = _compute(BATCH)
    assert r["status"] == "ok"
    assert calls == []
    assert r["graph_delta"]["written"] is False


def test_retry_returns_the_same_receipt():
    # a producer that crashed after sealing but before counting the batch emitted re-runs
    # the IDENTICAL batch → the memo returns the same receipt, not a duplicate
    first = _compute(BATCH)
    again = _compute(BATCH)
    assert again["memoized"] is True
    assert again["receipt"]["id"] == first["receipt"]["id"]
    assert len(receipts.chain("demo")) == 1


def test_the_kind_is_registered_and_discoverable():
    from compute_gateway import registry
    assert registry.KINDS["nugget-emit"]["status"] == "live"
    assert registry.KINDS["nugget-emit"]["executes_user_code"] is False
    kinds = client.get("/healthz").json()["kinds"]
    assert "nugget-emit" in kinds
