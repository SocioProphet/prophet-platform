"""Minimal Workspace Operation Plane runtime skeleton.

This module is intentionally small and contract-shaped. Canonical schemas live in
`SocioProphet/prophet-core-contracts`; this runtime consumes operation-like
mappings, validates a small set of state invariants, emits immutable events, and
materializes snapshots for fast reads.

It is not a policy engine, not a ledger, not a UI state store, and not a durable
backend. Those are explicit integration boundaries for later slices.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4


class OperationRuntimeError(RuntimeError):
    """Base runtime error for Workspace Operation skeleton failures."""


class StateTransitionError(OperationRuntimeError):
    """Raised when a command would violate the operation state machine."""


OPERATION_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"preflighting", "running", "canceled", "failed"},
    "preflighting": {"running", "blocked", "awaiting_decision", "failed", "canceled"},
    "awaiting_decision": {"running", "blocked", "canceled", "failed"},
    "blocked": {"awaiting_decision", "running", "failed", "canceled"},
    "running": {
        "paused",
        "retrying",
        "canceling",
        "failed",
        "completed",
        "completed_with_warnings",
        "blocked",
        "awaiting_decision",
    },
    "paused": {"running", "canceling", "failed"},
    "retrying": {"running", "failed", "blocked", "awaiting_decision"},
    "canceling": {"canceled", "completed_with_warnings", "compensated"},
    "failed": {"retrying", "compensated"},
    "completed": set(),
    "completed_with_warnings": set(),
    "canceled": {"compensated"},
    "compensated": set(),
}

TASK_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"preflighting", "running", "canceled", "failed"},
    "preflighting": {"running", "blocked", "awaiting_decision", "failed", "canceled"},
    "awaiting_decision": {"running", "blocked", "canceled", "failed"},
    "blocked": {"awaiting_decision", "running", "failed", "canceled"},
    "running": {
        "paused",
        "retrying",
        "canceling",
        "failed",
        "completed",
        "completed_with_warnings",
        "blocked",
        "awaiting_decision",
        "stale",
    },
    "paused": {"running", "canceling", "failed"},
    "retrying": {"running", "failed", "blocked", "awaiting_decision"},
    "canceling": {"canceled", "completed_with_warnings", "compensated"},
    "stale": {"running", "failed", "canceled"},
    "failed": {"retrying", "compensated"},
    "completed": set(),
    "completed_with_warnings": set(),
    "canceled": {"compensated"},
    "compensated": set(),
}

ARTIFACT_ADMISSION_TRANSITIONS: dict[str, set[str]] = {
    "not_stored": {"stored", "rejected"},
    "stored": {
        "quarantined",
        "pending_metadata",
        "pending_policy",
        "pending_encryption",
        "pending_scan",
        "admitted",
        "rejected",
        "archived",
    },
    "quarantined": {
        "pending_metadata",
        "pending_policy",
        "pending_encryption",
        "pending_scan",
        "admitted",
        "rejected",
        "archived",
    },
    "pending_metadata": {"pending_policy", "admitted", "rejected", "archived"},
    "pending_policy": {
        "admitted",
        "rejected",
        "archived",
        "pending_metadata",
        "pending_encryption",
        "pending_scan",
    },
    "pending_encryption": {"pending_policy", "admitted", "rejected", "archived"},
    "pending_scan": {"pending_policy", "admitted", "rejected", "archived"},
    "admitted": {"activated", "archived"},
    "activated": {"archived"},
    "rejected": {"archived"},
    "archived": set(),
}


@dataclass
class OperationRecord:
    """Materialized operation state."""

    operation: dict[str, Any]
    revision: int = 0
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    policy_gates: dict[str, dict[str, Any]] = field(default_factory=dict)


class InMemoryOperationRuntime:
    """Small in-memory runtime for early Operation Plane integration.

    The runtime accepts contract-shaped dictionaries and emits immutable event
    dictionaries. It is suitable for smoke tests, adapter development, and early
    UI projections. Production persistence, authorization, policy evaluation,
    ledger writes, and worker leases are intentionally not implemented here.
    """

    def __init__(self) -> None:
        self._records: dict[str, OperationRecord] = {}
        self._events: list[dict[str, Any]] = []
        self._idempotency_index: set[str] = set()

    @property
    def events(self) -> list[dict[str, Any]]:
        """Return a copy of all emitted events."""

        return deepcopy(self._events)

    def create_operation(self, operation: Mapping[str, Any]) -> dict[str, Any]:
        """Create an operation record and emit `workspace.operation.created`."""

        op = deepcopy(dict(operation))
        self._require_fields(op, ["operation_id", "operation_type", "actor", "status", "idempotency_key"])
        operation_id = op["operation_id"]
        if operation_id in self._records:
            raise OperationRuntimeError(f"operation already exists: {operation_id}")
        self._claim_idempotency(op["idempotency_key"])
        self._records[operation_id] = OperationRecord(operation=op)
        self._emit(operation_id, "workspace.operation.created", op.get("actor", self._system_actor()), {"operation_type": op["operation_type"]})
        return self.get_operation_snapshot(operation_id)

    def load_fixture_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        """Load a contract fixture bundle into runtime snapshots.

        This method is intended for downstream adapter development. It does not
        re-emit fixture-provided historical events; it creates a fresh runtime
        record from the bundle objects and emits a single loaded event.
        """

        operation = deepcopy(dict(bundle.get("operation") or {}))
        snapshot = self.create_operation(operation)
        operation_id = operation["operation_id"]
        record = self._records[operation_id]

        for task in self._objects(bundle, "task", "tasks"):
            self.attach_task(operation_id, task, emit=False)
        for artifact in self._objects(bundle, "artifact", "artifacts"):
            artifact_id = artifact.get("artifact_id")
            if not artifact_id:
                raise OperationRuntimeError("artifact missing artifact_id")
            record.artifacts[artifact_id] = deepcopy(artifact)
        for decision in self._objects(bundle, "decision", "decisions"):
            decision_id = decision.get("decision_id")
            if not decision_id:
                raise OperationRuntimeError("decision missing decision_id")
            record.decisions[decision_id] = deepcopy(decision)
        for gate in self._objects(bundle, "policy_gate", "policy_gates"):
            gate_id = gate.get("gate_id")
            if not gate_id:
                raise OperationRuntimeError("policy gate missing gate_id")
            record.policy_gates[gate_id] = deepcopy(gate)

        self._emit(operation_id, "workspace.operation.fixture_loaded", self._system_actor(), {"object_counts": self._object_counts(record)})
        return snapshot

    def attach_task(self, operation_id: str, task: Mapping[str, Any], *, emit: bool = True) -> dict[str, Any]:
        """Attach a task snapshot to an existing operation."""

        record = self._record(operation_id)
        task_obj = deepcopy(dict(task))
        self._require_fields(task_obj, ["task_id", "operation_id", "status", "idempotency_key"])
        if task_obj["operation_id"] != operation_id:
            raise OperationRuntimeError("task operation_id mismatch")
        self._claim_idempotency(task_obj["idempotency_key"])
        record.tasks[task_obj["task_id"]] = task_obj
        if emit:
            self._emit(operation_id, "workspace.operation.task_attached", self._system_actor(), {"task_id": task_obj["task_id"]})
        return self.get_operation_snapshot(operation_id)

    def transition_operation(self, operation_id: str, next_status: str, *, actor: Mapping[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
        """Transition an operation if allowed by v0.1 state rules."""

        record = self._record(operation_id)
        current = record.operation.get("status")
        self._assert_transition("operation", OPERATION_TRANSITIONS, current, next_status)
        record.operation["status"] = next_status
        record.operation["updated_at"] = self._now()
        record.revision += 1
        self._emit(operation_id, "workspace.operation.status_changed", actor or self._system_actor(), {"from": current, "to": next_status, "reason": reason})
        return self.get_operation_snapshot(operation_id)

    def transition_task(self, operation_id: str, task_id: str, next_status: str, *, actor: Mapping[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
        """Transition a task if allowed by v0.1 state rules."""

        record = self._record(operation_id)
        task = record.tasks.get(task_id)
        if task is None:
            raise OperationRuntimeError(f"unknown task: {task_id}")
        current = task.get("status")
        self._assert_transition("task", TASK_TRANSITIONS, current, next_status)
        if next_status == "retrying" and (not task.get("retryable") or not task.get("idempotency_key")):
            raise StateTransitionError(f"task {task_id} cannot retry without retryable=true and idempotency_key")
        task["status"] = next_status
        record.revision += 1
        self._emit(operation_id, "workspace.operation.task_status_changed", actor or self._system_actor(), {"task_id": task_id, "from": current, "to": next_status, "reason": reason})
        return self.get_operation_snapshot(operation_id)

    def cancel_operation(self, operation_id: str, *, actor: Mapping[str, Any] | None = None, reason: str = "cancel_requested") -> dict[str, Any]:
        """Cancel an operation through canceling -> canceled when possible."""

        record = self._record(operation_id)
        current = record.operation.get("status")
        if current != "canceling":
            self.transition_operation(operation_id, "canceling", actor=actor, reason=reason)
        return self.transition_operation(operation_id, "canceled", actor=actor, reason=reason)

    def retry_task(self, operation_id: str, task_id: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Retry a failed task when safe."""

        record = self._record(operation_id)
        task = record.tasks.get(task_id)
        if task is None:
            raise OperationRuntimeError(f"unknown task: {task_id}")
        if not task.get("retryable") or not task.get("idempotency_key"):
            raise StateTransitionError(f"task {task_id} is not safely retryable")
        return self.transition_task(operation_id, task_id, "retrying", actor=actor, reason="retry_requested")

    def admit_artifact(self, operation_id: str, artifact_id: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Mark an artifact as admitted if admission transition allows it."""

        return self._transition_artifact_admission(operation_id, artifact_id, "admitted", actor=actor)

    def quarantine_artifact(self, operation_id: str, artifact_id: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Mark an artifact as quarantined if admission transition allows it."""

        return self._transition_artifact_admission(operation_id, artifact_id, "quarantined", actor=actor)

    def activate_artifact(self, operation_id: str, artifact_id: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Activate an admitted artifact."""

        record = self._record(operation_id)
        artifact = record.artifacts.get(artifact_id)
        if artifact is None:
            raise OperationRuntimeError(f"unknown artifact: {artifact_id}")
        current = artifact.get("admission_state")
        if current not in {"admitted", "activated"}:
            raise StateTransitionError(f"artifact {artifact_id} cannot activate from {current}")
        artifact["admission_state"] = "activated"
        artifact["activation_state"] = "active"
        record.revision += 1
        self._emit(operation_id, "workspace.operation.artifact_activated", actor or self._system_actor(), {"artifact_id": artifact_id})
        return self.get_operation_snapshot(operation_id)

    def get_operation_snapshot(self, operation_id: str) -> dict[str, Any]:
        """Return a materialized operation snapshot."""

        record = self._record(operation_id)
        return {
            "schema_version": "0.1.0",
            "operation_id": operation_id,
            "status": record.operation.get("status"),
            "revision": record.revision,
            "updated_at": record.operation.get("updated_at") or self._now(),
            "task_counts": self._task_counts(record),
            "active_decision_ids": [decision_id for decision_id, decision in record.decisions.items() if decision.get("status") == "pending"],
            "artifact_ids": sorted(record.artifacts.keys()),
            "policy_gate_ids": sorted(record.policy_gates.keys()),
            "event_count": len([event for event in self._events if event.get("operation_id") == operation_id]),
        }

    def get_operation_detail(self, operation_id: str) -> dict[str, Any]:
        """Return full operation detail for inspectors and tests."""

        record = self._record(operation_id)
        return {
            "operation": deepcopy(record.operation),
            "tasks": deepcopy(record.tasks),
            "artifacts": deepcopy(record.artifacts),
            "decisions": deepcopy(record.decisions),
            "policy_gates": deepcopy(record.policy_gates),
            "snapshot": self.get_operation_snapshot(operation_id),
        }

    def _transition_artifact_admission(self, operation_id: str, artifact_id: str, next_state: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        record = self._record(operation_id)
        artifact = record.artifacts.get(artifact_id)
        if artifact is None:
            raise OperationRuntimeError(f"unknown artifact: {artifact_id}")
        current = artifact.get("admission_state")
        self._assert_transition("artifact", ARTIFACT_ADMISSION_TRANSITIONS, current, next_state)
        artifact["admission_state"] = next_state
        if next_state != "activated" and artifact.get("activation_state") == "active":
            raise StateTransitionError(f"artifact {artifact_id} active before admission")
        record.revision += 1
        self._emit(operation_id, "workspace.operation.artifact_admission_changed", actor or self._system_actor(), {"artifact_id": artifact_id, "from": current, "to": next_state})
        return self.get_operation_snapshot(operation_id)

    def _emit(self, operation_id: str, event_type: str, actor: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        self._events.append(
            {
                "schema_version": "0.1.0",
                "event_id": f"evt_{uuid4().hex}",
                "event_type": event_type,
                "operation_id": operation_id,
                "actor": deepcopy(dict(actor)),
                "occurred_at": self._now(),
                "payload": deepcopy(dict(payload)),
            }
        )

    def _record(self, operation_id: str) -> OperationRecord:
        try:
            return self._records[operation_id]
        except KeyError as exc:
            raise OperationRuntimeError(f"unknown operation: {operation_id}") from exc

    def _claim_idempotency(self, key: str) -> None:
        if key in self._idempotency_index:
            raise OperationRuntimeError(f"duplicate idempotency key: {key}")
        self._idempotency_index.add(key)

    @staticmethod
    def _require_fields(obj: Mapping[str, Any], fields: list[str]) -> None:
        missing = [field for field in fields if not obj.get(field)]
        if missing:
            raise OperationRuntimeError(f"missing required field(s): {', '.join(missing)}")

    @staticmethod
    def _assert_transition(kind: str, transitions: Mapping[str, set[str]], current: str | None, next_status: str) -> None:
        if current not in transitions:
            raise StateTransitionError(f"unknown {kind} status: {current}")
        if next_status not in transitions[current]:
            raise StateTransitionError(f"invalid {kind} transition: {current} -> {next_status}")

    @staticmethod
    def _objects(bundle: Mapping[str, Any], singular: str, plural: str) -> list[dict[str, Any]]:
        values: list[Any] = []
        if singular in bundle:
            values.append(bundle[singular])
        values.extend(bundle.get(plural) or [])
        return [deepcopy(value) for value in values if isinstance(value, dict)]

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _system_actor() -> dict[str, str]:
        return {"actor_type": "system", "actor_id": "workspace-operation-runtime"}

    @staticmethod
    def _task_counts(record: OperationRecord) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in record.tasks.values():
            status = str(task.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _object_counts(record: OperationRecord) -> dict[str, int]:
        return {
            "tasks": len(record.tasks),
            "artifacts": len(record.artifacts),
            "decisions": len(record.decisions),
            "policy_gates": len(record.policy_gates),
        }
