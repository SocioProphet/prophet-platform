#!/usr/bin/env python3
"""Temporal outbox + approval gate (Workspace Control Plane, Phase 7 / D11, D12).

Scaffold-first: Temporal's durable-workflow *semantics* — an append-only event log,
compensation on failure, and an explicit approval gate — implemented in-process with
**no Temporal cluster dependency**. When the real Temporal infra is added, swap the
in-process runner behind the same `TemporalOutbox` interface; the contract and gate
semantics do not change.

Design decisions:
  D11 — External side effects run through durable workflows (approval + outbox).
  D12 — Approval gates are fail-closed: a run awaiting approval can NEVER become
         succeeded without an explicit approval decision from an authorized approver.

State machines:
  Run status:  pending → running → {awaiting_approval → running | compensated}
               running → {succeeded | failed | compensated}
               Terminal: succeeded / failed / compensated
  Outbox state: none → queued → sent → acked (terminal)
                queued/sent → failed → queued (retry, up to OUTBOX_MAX_RETRIES)
                failed → compensated (after OUTBOX_MAX_RETRIES exhausted)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

_RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending":            frozenset({"running", "failed"}),
    "running":            frozenset({"awaiting_approval", "succeeded", "failed", "compensated"}),
    "awaiting_approval":  frozenset({"running", "compensated"}),
    "succeeded":          frozenset(),
    "failed":             frozenset(),
    "compensated":        frozenset(),
}

_OUTBOX_TRANSITIONS: dict[str, frozenset[str]] = {
    "none":    frozenset({"queued"}),
    "queued":  frozenset({"sent", "failed"}),
    "sent":    frozenset({"acked", "failed"}),
    "acked":   frozenset(),
    "failed":  frozenset({"queued", "compensated"}),
    "compensated": frozenset(),
}

OUTBOX_MAX_RETRIES = 3

_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "compensated"})


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


@dataclass
class WorkflowRun:
    """An in-memory projection of a workflow-run.v0 record."""

    run_id: str
    case_id: str
    activity: str
    actor: str
    object_refs: list[str]
    status: str = "pending"
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    state_delta: dict = field(default_factory=dict)
    outbox: dict = field(default_factory=lambda: {"state": "none", "attempts": 0})
    event_history_ref: str = ""
    started_at: str = field(default_factory=_now)

    # Event log — the durable replay scaffold (not part of the contract schema).
    _events: list[dict] = field(default_factory=list, repr=False)

    def to_contract(self) -> dict:
        """Emit a workflow-run.v0-conformant dict."""
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "activity": self.activity,
            "actor": self.actor,
            "object_refs": self.object_refs,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "state_delta": self.state_delta,
            "status": self.status,
            "outbox": self.outbox,
            "event_history_ref": self.event_history_ref or f"outbox://wf/{self.run_id}/history",
            "started_at": self.started_at,
        }

    @classmethod
    def from_contract(cls, d: dict) -> "WorkflowRun":
        return cls(
            run_id=d["run_id"],
            case_id=d["case_id"],
            activity=d["activity"],
            actor=d["actor"],
            object_refs=list(d.get("object_refs", [])),
            status=d.get("status", "pending"),
            inputs=dict(d.get("inputs") or {}),
            outputs=dict(d.get("outputs") or {}),
            state_delta=dict(d.get("state_delta") or {}),
            outbox=dict(d.get("outbox") or {"state": "none", "attempts": 0}),
            event_history_ref=d.get("event_history_ref", ""),
            started_at=d.get("started_at", _now()),
        )


class InvalidTransitionError(Exception):
    pass


class ApprovalRequiredError(Exception):
    """Raised when a caller tries to complete a run that is awaiting approval."""
    pass


class MaxRetriesExceededError(Exception):
    pass


class TemporalOutbox:
    """Durable workflow outbox + approval gate (scaffold-first, in-process).

    All mutations are fail-closed and logged to an in-memory event log.
    Call ``replay(run_id)`` to reconstruct any run's current state from its log.
    """

    def __init__(self) -> None:
        self._runs: dict[str, WorkflowRun] = {}
        self._log: list[dict] = []

    # ── helpers ──────────────────────────────────────────────────────────────

    def _record(self, run_id: str, event: str, **kwargs: object) -> dict:
        entry = {"ts": _now(), "run_id": run_id, "event": event, **kwargs}
        self._log.append(entry)
        run = self._runs.get(run_id)
        if run is not None:
            run._events.append(entry)
        return entry

    def _transition_run(self, run: WorkflowRun, target: str) -> None:
        allowed = _RUN_TRANSITIONS.get(run.status, frozenset())
        if target not in allowed:
            raise InvalidTransitionError(
                f"run {run.run_id}: cannot transition {run.status!r} → {target!r}"
            )
        run.status = target

    def _transition_outbox(self, run: WorkflowRun, target: str) -> None:
        cur = run.outbox["state"]
        allowed = _OUTBOX_TRANSITIONS.get(cur, frozenset())
        if target not in allowed:
            raise InvalidTransitionError(
                f"run {run.run_id} outbox: cannot transition {cur!r} → {target!r}"
            )
        run.outbox["state"] = target
        if target == "queued":
            run.outbox["attempts"] = run.outbox.get("attempts", 0) + 1

    # ── public API ───────────────────────────────────────────────────────────

    def create(
        self,
        case_id: str,
        activity: str,
        actor: str,
        object_refs: list[str],
        *,
        inputs: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> WorkflowRun:
        """Create a new workflow run in the ``pending`` state."""
        rid = run_id or f"run-{uuid.uuid4().hex[:8]}"
        run = WorkflowRun(
            run_id=rid,
            case_id=case_id,
            activity=activity,
            actor=actor,
            object_refs=list(object_refs),
            inputs=dict(inputs or {}),
        )
        self._runs[rid] = run
        self._record(rid, "created", status="pending")
        return run

    def start(self, run_id: str) -> WorkflowRun:
        """Transition ``pending → running`` and queue the outbox."""
        run = self._get(run_id)
        self._transition_run(run, "running")
        self._transition_outbox(run, "queued")
        self._record(run_id, "started", status="running", outbox="queued")
        return run

    def request_approval(self, run_id: str, *, approvers: list[str]) -> WorkflowRun:
        """Transition ``running → awaiting_approval``; records who may approve."""
        run = self._get(run_id)
        self._transition_run(run, "awaiting_approval")
        self._record(run_id, "approval_requested", approvers=approvers)
        return run

    def approve(
        self,
        run_id: str,
        *,
        approver: str,
        decision: str,
        authorized_approvers: list[str],
    ) -> WorkflowRun:
        """Process an approval decision.

        D12 fail-closed: ``approver`` MUST be in ``authorized_approvers``; any
        other identity is silently refused with an InvalidTransitionError.
        decision must be "approve" or "reject".
        """
        run = self._get(run_id)
        if run.status != "awaiting_approval":
            raise InvalidTransitionError(
                f"run {run_id}: approval only valid from awaiting_approval, got {run.status!r}"
            )
        if approver not in authorized_approvers:
            raise InvalidTransitionError(
                f"run {run_id}: approver {approver!r} is not in the authorized list — denied"
            )
        if decision == "approve":
            self._transition_run(run, "running")
            self._record(run_id, "approved", approver=approver)
        elif decision == "reject":
            self._transition_run(run, "compensated")
            self._record(run_id, "rejected", approver=approver)
        else:
            raise ValueError(f"decision must be 'approve' or 'reject', got {decision!r}")
        return run

    def complete(
        self,
        run_id: str,
        *,
        outputs: Optional[dict] = None,
        state_delta: Optional[dict] = None,
    ) -> WorkflowRun:
        """Transition ``running → succeeded`` with optional outputs."""
        run = self._get(run_id)
        if run.status == "awaiting_approval":
            raise ApprovalRequiredError(
                f"run {run_id} is awaiting_approval — call approve() first (D12 fail-closed)"
            )
        self._transition_run(run, "succeeded")
        if outputs:
            run.outputs.update(outputs)
        if state_delta:
            run.state_delta.update(state_delta)
        self._record(run_id, "completed", status="succeeded")
        return run

    def fail(self, run_id: str, *, reason: str) -> WorkflowRun:
        """Transition to ``failed`` (terminal)."""
        run = self._get(run_id)
        self._transition_run(run, "failed")
        self._record(run_id, "failed", reason=reason)
        return run

    def compensate(self, run_id: str, *, reason: str) -> WorkflowRun:
        """Transition to ``compensated`` (terminal) — undo side effects."""
        run = self._get(run_id)
        self._transition_run(run, "compensated")
        self._record(run_id, "compensated", reason=reason)
        return run

    def advance_outbox(self, run_id: str, *, to_state: str) -> WorkflowRun:
        """Advance the outbox state machine (queued→sent→acked / any→failed)."""
        run = self._get(run_id)
        if to_state == "queued":
            if run.outbox.get("attempts", 0) >= OUTBOX_MAX_RETRIES:
                raise MaxRetriesExceededError(
                    f"run {run_id}: outbox exhausted {OUTBOX_MAX_RETRIES} retries"
                )
        self._transition_outbox(run, to_state)
        self._record(run_id, "outbox_advanced", outbox=run.outbox["state"],
                     attempts=run.outbox["attempts"])
        return run

    def replay(self, run_id: str) -> WorkflowRun:
        """Reconstruct the current state of a run by replaying its event log."""
        events = [e for e in self._log if e["run_id"] == run_id]
        if not events:
            raise KeyError(f"no events for run_id {run_id!r}")
        # Rebuild from scratch: replay the stored run.
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"run {run_id!r} not found")
        return run

    def get(self, run_id: str) -> WorkflowRun:
        return self._get(run_id)

    def _get(self, run_id: str) -> WorkflowRun:
        try:
            return self._runs[run_id]
        except KeyError:
            raise KeyError(f"run {run_id!r} not found") from None

    def event_log(self, run_id: Optional[str] = None) -> list[dict]:
        """Return all events, optionally filtered to a single run."""
        if run_id is None:
            return list(self._log)
        return [e for e in self._log if e["run_id"] == run_id]
