"""Workspace Operation adapter registry skeleton.

Adapters implement operation-type-specific decomposition and execution. This file
only records adapter declarations and validates that operation types do not
silently overlap. Real upload/import, memory, terminal, browser, sync, release,
and security exercise adapters belong in their owning repos or follow-on
platform modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class OperationAdapterError(RuntimeError):
    """Raised for adapter registry failures."""


class OperationAdapter(Protocol):
    """Protocol for operation adapters.

    v0.1 adapters should be thin: declare capabilities, perform preflight or
    task decomposition, and emit contract-shaped task/artifact objects back to
    the runtime. They should not own the global operation lifecycle.
    """

    @property
    def operation_type(self) -> str:
        """Operation type handled by this adapter."""

    def declaration(self) -> Mapping[str, Any]:
        """Return an AdapterContract-shaped declaration."""

    def preflight(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return preflight result metadata."""

    def decompose(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return contract-shaped tasks/artifacts/decisions/gates for operation."""


@dataclass(frozen=True)
class StaticAdapterDeclaration:
    """Small declaration-only adapter useful for tests and early wiring."""

    operation_type: str
    supported_artifact_types: tuple[str, ...]
    idempotency_behavior: str = "required"
    retry_behavior: str = "idempotent"
    emitted_event_types: tuple[str, ...] = ("workspace.operation.task_started",)
    required_capabilities: tuple[str, ...] = ()
    policy_gates_invoked: tuple[str, ...] = ()
    diagnostic_redaction_rules: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)

    def declaration(self) -> Mapping[str, Any]:
        return {
            "schema_version": "0.1.0",
            "operation_type": self.operation_type,
            "supported_artifact_types": list(self.supported_artifact_types),
            "required_capabilities": list(self.required_capabilities),
            "policy_gates_invoked": list(self.policy_gates_invoked),
            "idempotency_behavior": self.idempotency_behavior,
            "retry_behavior": self.retry_behavior,
            "pause_resume_behavior": "adapter_defined",
            "cancel_behavior": "supported",
            "compensation_behavior": "adapter_defined",
            "progress_semantics": "adapter-defined staged progress",
            "emitted_event_types": list(self.emitted_event_types),
            "diagnostic_redaction_rules": list(self.diagnostic_redaction_rules),
            "test_fixtures": list(self.extra.get("test_fixtures", [])),
        }

    def preflight(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "operation_type": self.operation_type,
            "status": "passed",
            "required_capabilities": list(self.required_capabilities),
        }

    def decompose(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "operation_id": operation.get("operation_id"),
            "operation_type": self.operation_type,
            "tasks": [],
            "artifacts": [],
            "decisions": [],
            "policy_gates": [],
        }


class OperationAdapterRegistry:
    """Registry for operation adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, OperationAdapter] = {}

    def register(self, adapter: OperationAdapter) -> None:
        operation_type = adapter.operation_type
        if not operation_type:
            raise OperationAdapterError("adapter operation_type is required")
        if operation_type in self._adapters:
            raise OperationAdapterError(f"adapter already registered for operation_type: {operation_type}")
        self._adapters[operation_type] = adapter

    def get(self, operation_type: str) -> OperationAdapter:
        try:
            return self._adapters[operation_type]
        except KeyError as exc:
            raise OperationAdapterError(f"no adapter registered for operation_type: {operation_type}") from exc

    def has(self, operation_type: str) -> bool:
        return operation_type in self._adapters

    def declarations(self) -> list[Mapping[str, Any]]:
        return [adapter.declaration() for adapter in self._adapters.values()]

    def operation_types(self) -> list[str]:
        return sorted(self._adapters.keys())
