"""Provenance is append-only and its receipt chain verifies (section 8).

Receipts are minted with the same eleven-field body and the same canonical JSON
encoding as compute_gateway.receipts, so an impairment run is evidence in the estate's
existing chain rather than a private log format. These tests pin that contract.
"""

from __future__ import annotations

import json
import time

from noetica_impair.provenance.log import (
    RunLog, RunRecord, mint_receipt, new_run_id, sha, verify_chain,
)


def make_record(i: int) -> RunRecord:
    return RunRecord(
        run_id=new_run_id(), ts=time.time(), model_key="toy-dense", arch="dense",
        driver="mechanical", dose=i * 0.2, seed=7, substance_preset="ALCOHOL",
        faculty_vector={"competence": 1.0 - i * 0.1, "fluency": 0.99},
    )


def test_chain_verifies(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl")
    for i in range(5):
        log.append(make_record(i))
    ok, msg = verify_chain(log.read_all())
    assert ok, msg
    assert "5 receipts verified" in msg


def test_receipt_id_is_sha_of_exactly_eleven_fields():
    r = mint_receipt(
        project="p", kind="impairment-run", backend="local", runtime="rt",
        inputs={"a": 1}, outputs={"b": 2}, status="ok", actor="me",
        epistemic_status="observed", prev=None,
    )
    body = {
        "project": r.project, "kind": r.kind, "backend": r.backend, "runtime": r.runtime,
        "inputs_sha": r.inputs_sha, "outputs_sha": r.outputs_sha, "status": r.status,
        "actor": r.actor, "epistemic_status": r.epistemic_status, "prev": r.prev, "ts": r.ts,
    }
    assert sha(body) == r.id


def test_tampering_is_detected(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl")
    for i in range(3):
        log.append(make_record(i))
    records = log.read_all()
    records[1]["receipt"]["outputs_sha"] = sha({"faked": True})
    ok, msg = verify_chain(records)
    assert not ok and "tampered" in msg


def test_broken_link_is_detected(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl")
    for i in range(3):
        log.append(make_record(i))
    records = log.read_all()
    del records[1]
    ok, msg = verify_chain(records)
    assert not ok and "breaks the chain" in msg


def test_append_only_never_rewrites(tmp_path):
    p = tmp_path / "runs.jsonl"
    log = RunLog(p)
    log.append(make_record(0))
    first = p.read_text()
    log.append(make_record(1))
    assert p.read_text().startswith(first), "existing lines were rewritten"


def test_chain_resumes_across_processes(tmp_path):
    """A second RunLog on the same file must continue the chain, not fork it."""
    p = tmp_path / "runs.jsonl"
    a = RunLog(p)
    a.append(make_record(0))
    a.append(make_record(1))
    b = RunLog(p)               # simulates a new process / a resumed sweep
    b.append(make_record(2))
    ok, msg = verify_chain(RunLog(p).read_all())
    assert ok, msg


def test_raw_output_withheld_by_default(tmp_path):
    rec = make_record(0)
    rec.raw_outputs = ["some generated text"]
    log = RunLog(tmp_path / "runs.jsonl")               # retain_raw defaults False
    log.append(rec)
    stored = json.loads((tmp_path / "runs.jsonl").read_text().strip())
    assert stored["raw_outputs"] is None

    rec2 = make_record(1)
    rec2.raw_outputs = ["kept"]
    log2 = RunLog(tmp_path / "raw.jsonl", retain_raw=True)
    log2.append(rec2)
    stored2 = json.loads((tmp_path / "raw.jsonl").read_text().strip())
    assert stored2["raw_outputs"] == ["kept"]
