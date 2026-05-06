"""Workspace Operation command helpers.

The canonical command vocabulary lives in `prophet-core-contracts`. These helper
functions create command-shaped dictionaries for early runtime and adapter tests.
They intentionally avoid becoming a separate schema authority.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

COMMAND_TYPES = {
    "CreateOperation",
    "PreflightOperation",
    "StartOperation",
    "PauseOperation",
    "ResumeOperation",
    "CancelOperation",
    "RetryTask",
    "RetryOperation",
    "ResolveDecision",
    "AttachArtifact",
    "AdmitArtifact",
    "QuarantineArtifact",
    "ActivateArtifact",
    "CompensateOperation",
    "ExportDiagnostics",
    "RequestOverride",
}


def make_command(
    command_type: str,
    *,
    operation_id: str,
    actor: Mapping[str, Any],
    task_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create an OperationCommand-shaped dictionary."""

    if command_type not in COMMAND_TYPES:
        raise ValueError(f"unknown command_type: {command_type}")
    command: dict[str, Any] = {
        "schema_version": "0.1.0",
        "command_id": f"cmd_{uuid4().hex}",
        "command_type": command_type,
        "operation_id": operation_id,
        "actor": dict(actor),
        "issued_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "idempotency_key": idempotency_key or f"idem_cmd_{uuid4().hex}",
        "payload": dict(payload or {}),
    }
    if task_id:
        command["task_id"] = task_id
    return command


def create_operation_command(operation: Mapping[str, Any], *, actor: Mapping[str, Any]) -> dict[str, Any]:
    """Create a CreateOperation command for an operation payload."""

    operation_id = str(operation.get("operation_id", ""))
    if not operation_id:
        raise ValueError("operation.operation_id is required")
    return make_command(
        "CreateOperation",
        operation_id=operation_id,
        actor=actor,
        payload={"operation": dict(operation)},
        idempotency_key=str(operation.get("idempotency_key") or ""),
    )


def retry_task_command(operation_id: str, task_id: str, *, actor: Mapping[str, Any]) -> dict[str, Any]:
    """Create a RetryTask command."""

    return make_command("RetryTask", operation_id=operation_id, task_id=task_id, actor=actor)


def cancel_operation_command(operation_id: str, *, actor: Mapping[str, Any], reason: str = "cancel_requested") -> dict[str, Any]:
    """Create a CancelOperation command."""

    return make_command("CancelOperation", operation_id=operation_id, actor=actor, payload={"reason": reason})


def admit_artifact_command(operation_id: str, artifact_id: str, *, actor: Mapping[str, Any]) -> dict[str, Any]:
    """Create an AdmitArtifact command."""

    return make_command("AdmitArtifact", operation_id=operation_id, actor=actor, payload={"artifact_id": artifact_id})


def activate_artifact_command(operation_id: str, artifact_id: str, *, actor: Mapping[str, Any]) -> dict[str, Any]:
    """Create an ActivateArtifact command."""

    return make_command("ActivateArtifact", operation_id=operation_id, actor=actor, payload={"artifact_id": artifact_id})
