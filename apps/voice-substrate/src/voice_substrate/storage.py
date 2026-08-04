"""Transcript storage — the "storage + audit log" half of framework §10.3 step 1.

One rule, enforced structurally rather than by convention: this store REFUSES to persist a
result whose redaction stage did not run. Storage is where an un-redacted transcript stops
being a transient in-memory value and becomes a durable disclosure, so it is the right
place for a hard gate.

The persisted artifact contains the redacted text, the value-free redaction manifest, and
the audit log. It never contains the raw transcript, because the raw transcript is
destroyed inside the pipeline (see pipeline.py) before a result object exists.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .types import PipelineResult


class UnredactedWriteRefused(RuntimeError):
    """Raised when something tries to store a result that has not been redacted."""


class TranscriptStore(Protocol):
    def put(self, result: PipelineResult, metadata: dict[str, Any] | None = None) -> str: ...


class FilesystemTranscriptStore:
    """JSON-per-transcript on local disk. Adequate for a substrate service; swap for
    object storage without touching the pipeline (it depends on the Protocol only)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, result: PipelineResult, metadata: dict[str, Any] | None = None) -> str:
        if not result.redaction_applied or result.redaction is None:
            raise UnredactedWriteRefused(
                "refusing to persist a transcript whose redaction stage did not run — "
                "storage is a durable disclosure and redaction is not optional"
            )
        transcript_id = uuid.uuid4().hex
        payload = {
            "transcript_id": transcript_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            **result.to_dict(),
        }
        (self.root / f"{transcript_id}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        return transcript_id


class InMemoryTranscriptStore:
    """Same contract, no disk. Used by tests and by the service when no store root is set."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def put(self, result: PipelineResult, metadata: dict[str, Any] | None = None) -> str:
        if not result.redaction_applied or result.redaction is None:
            raise UnredactedWriteRefused(
                "refusing to persist a transcript whose redaction stage did not run"
            )
        transcript_id = uuid.uuid4().hex
        self.items[transcript_id] = {
            "transcript_id": transcript_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            **result.to_dict(),
        }
        return transcript_id
