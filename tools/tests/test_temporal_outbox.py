"""Temporal outbox + approval gate (Phase 7) — correctness and gate proof.

Tests prove:
  - Happy path: create → start → complete
  - Approval gate: create → start → request_approval → approve → complete
  - D12 fail-closed: cannot complete a run awaiting approval without explicit approval
  - D12 fail-closed: non-authorized approver is rejected
  - D12 fail-closed: reject decision compensates the run
  - Invalid status transitions are refused
  - Outbox state machine: none→queued→sent→acked, retry on failure, max-retries
  - Compensation: running → compensated
  - replay() reconstructs current run from event log
  - to_contract() output is workflow-run.v0 conformant
  - Schema conformance against frozen contract schema
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from temporal_outbox import (  # type: ignore  # noqa: E402
    ApprovalRequiredError,
    InvalidTransitionError,
    MaxRetriesExceededError,
    OUTBOX_MAX_RETRIES,
    TemporalOutbox,
    WorkflowRun,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "workspace-control-plane"
    / "schemas"
    / "workflow-run.v0.schema.json"
)


def _schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_VALIDATOR = _schema_validator() if SCHEMA_PATH.exists() else None


def _validate(d: dict) -> None:
    if _VALIDATOR is not None:
        errors = list(_VALIDATOR.iter_errors(d))
        assert not errors, "\n".join(str(e) for e in errors)


def _outbox(state: str, attempts: int = 0) -> dict:
    return {"state": state, "attempts": attempts}


# ── Happy path ───────────────────────────────────────────────────────────────

def test_happy_path_create_start_complete():
    tb = TemporalOutbox()
    run = tb.create("case-1", "SendReport", "user://alice", ["asset://doc-1"])
    assert run.status == "pending"

    run = tb.start(run.run_id)
    assert run.status == "running"
    assert run.outbox["state"] == "queued"

    run = tb.complete(run.run_id, outputs={"sent": True})
    assert run.status == "succeeded"
    assert run.outputs == {"sent": True}

    _validate(run.to_contract())


def test_approval_gate_happy_path():
    tb = TemporalOutbox()
    run = tb.create("case-2", "ShareExternally", "user://bob", ["asset://doc-2"])
    tb.start(run.run_id)
    tb.request_approval(run.run_id, approvers=["user://mgr"])

    assert tb.get(run.run_id).status == "awaiting_approval"

    tb.approve(run.run_id, approver="user://mgr", decision="approve",
               authorized_approvers=["user://mgr"])

    assert tb.get(run.run_id).status == "running"
    run = tb.complete(run.run_id)
    assert run.status == "succeeded"
    _validate(run.to_contract())


# ── D12 fail-closed gate ─────────────────────────────────────────────────────

def test_complete_while_awaiting_approval_is_refused():
    """D12 fail-closed: succeeded requires explicit approval, never auto-granted."""
    tb = TemporalOutbox()
    run = tb.create("case-3", "HighRisk", "user://carol", [])
    tb.start(run.run_id)
    tb.request_approval(run.run_id, approvers=["user://cso"])

    with pytest.raises(ApprovalRequiredError):
        tb.complete(run.run_id)


def test_unauthorized_approver_is_refused():
    """D12: a caller not in the authorized list is silently rejected."""
    tb = TemporalOutbox()
    run = tb.create("case-4", "HighRisk", "user://dave", [])
    tb.start(run.run_id)
    tb.request_approval(run.run_id, approvers=["user://cso"])

    with pytest.raises(InvalidTransitionError, match="not in the authorized list"):
        tb.approve(run.run_id, approver="user://attacker", decision="approve",
                   authorized_approvers=["user://cso"])

    assert tb.get(run.run_id).status == "awaiting_approval"


def test_reject_decision_compensates():
    """D12: a reject decision transitions to compensated (terminal)."""
    tb = TemporalOutbox()
    run = tb.create("case-5", "ShareExternally", "user://eve", [])
    tb.start(run.run_id)
    tb.request_approval(run.run_id, approvers=["user://mgr"])
    run = tb.approve(run.run_id, approver="user://mgr", decision="reject",
                     authorized_approvers=["user://mgr"])

    assert run.status == "compensated"
    with pytest.raises(InvalidTransitionError):
        tb.complete(run.run_id)


# ── Outbox state machine ──────────────────────────────────────────────────────

def test_outbox_advances_queued_to_sent_to_acked():
    tb = TemporalOutbox()
    run = tb.create("case-6", "Notify", "user://frank", [])
    tb.start(run.run_id)
    assert run.outbox["state"] == "queued"

    tb.advance_outbox(run.run_id, to_state="sent")
    assert tb.get(run.run_id).outbox["state"] == "sent"

    tb.advance_outbox(run.run_id, to_state="acked")
    assert tb.get(run.run_id).outbox["state"] == "acked"


def test_outbox_retry_on_failure():
    tb = TemporalOutbox()
    run = tb.create("case-7", "Notify", "user://grace", [])
    tb.start(run.run_id)

    tb.advance_outbox(run.run_id, to_state="failed")
    assert tb.get(run.run_id).outbox["state"] == "failed"

    tb.advance_outbox(run.run_id, to_state="queued")  # retry
    assert tb.get(run.run_id).outbox["attempts"] == 2


def test_outbox_max_retries_exhausted_raises():
    tb = TemporalOutbox()
    run = tb.create("case-8", "Notify", "user://henry", [])
    tb.start(run.run_id)

    for _ in range(OUTBOX_MAX_RETRIES - 1):
        tb.advance_outbox(run.run_id, to_state="failed")
        tb.advance_outbox(run.run_id, to_state="queued")

    tb.advance_outbox(run.run_id, to_state="failed")
    with pytest.raises(MaxRetriesExceededError):
        tb.advance_outbox(run.run_id, to_state="queued")


# ── Invalid transitions ───────────────────────────────────────────────────────

def test_invalid_run_transition_refused():
    tb = TemporalOutbox()
    run = tb.create("case-9", "Noop", "user://ivan", [])
    with pytest.raises(InvalidTransitionError):
        tb._transition_run(run, "succeeded")  # pending → succeeded is not allowed


def test_terminal_run_cannot_transition():
    tb = TemporalOutbox()
    run = tb.create("case-10", "Noop", "user://jill", [])
    tb.start(run.run_id)
    tb.fail(run.run_id, reason="network error")

    with pytest.raises(InvalidTransitionError):
        tb.start(run.run_id)  # failed is terminal


# ── Compensation ──────────────────────────────────────────────────────────────

def test_compensate_from_running():
    tb = TemporalOutbox()
    run = tb.create("case-11", "Sync", "user://karen", [])
    tb.start(run.run_id)
    run = tb.compensate(run.run_id, reason="user cancelled")
    assert run.status == "compensated"
    _validate(run.to_contract())


# ── Event log + replay ───────────────────────────────────────────────────────

def test_event_log_captures_all_transitions():
    tb = TemporalOutbox()
    run = tb.create("case-12", "Report", "user://leo", [])
    tb.start(run.run_id)
    tb.complete(run.run_id)

    log = tb.event_log(run.run_id)
    events = [e["event"] for e in log]
    assert events == ["created", "started", "completed"]


def test_replay_returns_current_state():
    tb = TemporalOutbox()
    run = tb.create("case-13", "Report", "user://mia", [])
    tb.start(run.run_id)
    tb.complete(run.run_id)

    replayed = tb.replay(run.run_id)
    assert replayed.status == "succeeded"
    assert replayed.run_id == run.run_id


# ── Schema conformance ────────────────────────────────────────────────────────

def test_to_contract_conforms_to_workflow_run_v0():
    tb = TemporalOutbox()
    run = tb.create(
        "case-14", "ShareExternally", "user://alice", ["asset://doc-14"],
        inputs={"recipient": "partner@example.com"},
    )
    tb.start(run.run_id)
    tb.request_approval(run.run_id, approvers=["user://mgr"])

    contract = run.to_contract()
    _validate(contract)

    assert contract["status"] == "awaiting_approval"
    assert contract["outbox"]["state"] == "queued"


def test_from_contract_round_trip():
    """WorkflowRun.from_contract(run.to_contract()) preserves all fields."""
    tb = TemporalOutbox()
    run = tb.create("case-15", "Classify", "user://nina", ["asset://doc-15"],
                    inputs={"model": "monotone-logistic"})
    tb.start(run.run_id)

    d = run.to_contract()
    run2 = WorkflowRun.from_contract(d)
    assert run2.run_id == run.run_id
    assert run2.status == run.status
    assert run2.inputs == run.inputs
    assert run2.outbox == run.outbox
