"""Impairment runs render into Noetica's NoeticaTaskResult contract.

Noetica owns the governance-trail rendering; it does not own policy admission,
routing, or evidence authority. These tests pin that the envelope claims only what it
is entitled to claim.
"""

from __future__ import annotations

import time

import pytest

from noetica_impair.conformance.noetica import (
    SCHEMA_VERSION, TaskResultInputs, requires_policy_decision, task_result,
)
from noetica_impair.provenance.log import RunLog, RunRecord, new_run_id
from noetica_impair.readout.metrics import DissociationMatrix, FacultyVector


@pytest.fixture
def record(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl")
    rec = RunRecord(
        run_id=new_run_id(), ts=time.time(), model_key="gemma2-9b", arch="dense",
        driver="mechanical", dose=0.6, seed=11, substance_preset="ALCOHOL",
        interventions=[{"kind": "sae_steer"}, {"kind": "residual_noise"}],
        faculty_vector={},
    )
    return log.append(rec)


def base_inputs(**kw) -> TaskResultInputs:
    kw.setdefault("session_id", "sess-1")
    kw.setdefault("request_hash", "sha256:deadbeef")
    return TaskResultInputs(**kw)


FV = FacultyVector(consistency=0.6, calibration=0.5, lookahead=0.7,
                   working_memory=0.4, fluency=0.97, competence=0.45)


def test_envelope_has_the_contract_fields(record):
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs())
    # Field set from Noetica/lib/types/task.ts NoeticaTaskResult.
    for k in ("schema_version", "status", "run_id", "content", "model_routed",
              "provider", "model_overridden", "policy_admitted", "grant_refs",
              "memory_written", "latency_ms"):
        assert k in r
    assert r["schema_version"] == SCHEMA_VERSION
    assert r["status"] == "success"


def test_policy_admitted_is_false_without_a_decision(record):
    """Defaulting this to True would fabricate a governance fact."""
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs())
    assert r["policy_admitted"] is False


def test_policy_admitted_is_true_only_with_a_real_decision_ref(record):
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it",
                    inputs=base_inputs(policy_decision_ref="urn:srcos:exec-decision:abc"))
    assert r["policy_admitted"] is True
    assert r["policy_ref"] == "urn:srcos:exec-decision:abc"


def test_feature_steering_without_a_decision_is_called_out(record):
    """v0 gates feature_steering on a policy decision; silence would be an over-claim."""
    assert requires_policy_decision(["sae_steer"])
    assert not requires_policy_decision(["residual_noise", "logit_ops"])
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs())
    assert "un-admitted evidence" in r["content"]


def test_evidence_ref_is_the_receipt(record):
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs())
    assert r["evidence_ref"] == record.receipt["id"]
    assert r["evidence_hash"] == record.receipt["outputs_sha"]


def test_no_authority_is_claimed_that_noetica_delegates(record):
    """Routing, memory and grants belong to other planes -- claim none of them."""
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it",
                    inputs=base_inputs(tool_grant_refs=("grant-a", "grant-b"),
                                       resolved_grant_refs=("grant-a",)))
    assert r["model_overridden"] is False
    assert r["memory_written"] is False
    assert r["grant_refs"]["missing"] == ["grant-b"]


def test_content_names_the_dissociation_signature(record):
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs())
    assert "competence fell while fluency held" in r["content"]


def test_content_flags_a_coarse_lesion(record):
    coarse = FacultyVector(fluency=0.45, competence=0.45, consistency=0.5,
                           calibration=0.5, lookahead=0.5, working_memory=0.5)
    r = task_result(run_record=record, faculty=coarse, label="BLUNT",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs())
    assert "coarse lesion" in r["content"]


def test_verdict_is_appended_when_supplied(record):
    m = DissociationMatrix(dose=0.6)
    m.add("A", FacultyVector(consistency=0.4, working_memory=0.3))
    m.add("B", FacultyVector(lookahead=0.2, calibration=0.35))
    r = task_result(run_record=record, faculty=FV, label="ALCOHOL",
                    model_id="google/gemma-2-9b-it", inputs=base_inputs(),
                    verdict=m.check())
    assert "DISSOCIATION" in r["content"]
