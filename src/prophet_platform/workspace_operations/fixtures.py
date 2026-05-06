"""Fixture adapters for early Workspace Operation runtime wiring.

These adapters are not production implementations. They provide contract-shaped
policy and ledger seams for tests, demos, and downstream integration work while
`policy-fabric` and `prophet-core-ledger` define real implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .boundaries import BoundaryResult


@dataclass
class FixturePolicyClient:
    """Policy client that returns configured boundary decisions.

    Decisions are keyed by command type. Missing command types default to allow.
    Optional gate records are retained for inspector/ledger-facing tests.
    """

    decisions: dict[str, BoundaryResult] = field(default_factory=dict)
    gate_records: list[dict[str, Any]] = field(default_factory=list)

    def evaluate_command(self, command: Mapping[str, Any], operation: Mapping[str, Any] | None = None) -> BoundaryResult:
        command_type = str(command.get("command_type", ""))
        return self.decisions.get(command_type, BoundaryResult(allowed=True, reason="fixture policy allow"))

    def add_gate_record(
        self,
        *,
        gate_id: str,
        operation_id: str,
        gate_type: str,
        status: str,
        explanation: str,
        responsible_actor: str = "system",
        remediation_options: tuple[str, ...] = (),
        artifact_id: str | None = None,
        audit_required: bool = True,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": "0.1.0",
            "gate_id": gate_id,
            "operation_id": operation_id,
            "gate_type": gate_type,
            "status": status,
            "explanation": explanation,
            "responsible_actor": responsible_actor,
            "remediation_options": list(remediation_options),
            "audit_required": audit_required,
            "evidence_refs": [],
        }
        if artifact_id:
            record["artifact_id"] = artifact_id
        self.gate_records.append(record)
        return record


@dataclass
class CollectingLedgerSink:
    """Ledger sink that collects events and derives evidence records."""

    events: list[dict[str, Any]] = field(default_factory=list)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)

    def record_event(self, event: Mapping[str, Any]) -> None:
        event_dict = dict(event)
        self.events.append(event_dict)
        self.evidence_records.append(self.to_evidence_record(event_dict))

    @staticmethod
    def to_evidence_record(event: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "0.1.0",
            "evidence_type": "OperationEventLedgerEntry",
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "operation_id": event.get("operation_id"),
            "actor": event.get("actor"),
            "occurred_at": event.get("occurred_at"),
            "trace_id": event.get("trace_id"),
            "payload": event.get("payload", {}),
            "redaction_status": "not_applicable",
        }


@dataclass
class FixtureAgentAuthorityHook:
    """Agent authority hook keyed by actor/action pairs.

    Missing actor/action pairs default to allow. Use `deny()` to model explicit
    authority failures without importing the real Agent Registry.
    """

    decisions: dict[tuple[str, str], BoundaryResult] = field(default_factory=dict)

    def authorize_actor(self, actor: Mapping[str, Any], action: str, resource: Mapping[str, Any]) -> BoundaryResult:
        actor_id = str(actor.get("actor_id", ""))
        return self.decisions.get((actor_id, action), BoundaryResult(allowed=True, reason="fixture authority allow"))

    def deny(self, actor_id: str, action: str, *, reason: str = "fixture authority denial") -> None:
        self.decisions[(actor_id, action)] = BoundaryResult(
            allowed=False,
            reason=reason,
            responsible_actor="agent_operator",
            remediation_options=("review_agent_scope",),
        )
