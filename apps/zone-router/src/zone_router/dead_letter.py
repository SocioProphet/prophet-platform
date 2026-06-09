"""
Dead-letter artifact writer for zone publication outcomes.

When a publication attempt is terminal (all retry attempts exhausted),
a dead-letter artifact is written alongside the failure evidence.

Dead-letter artifacts are observability and audit records only.
They do not authorize remediation, they do not trigger remote mutation,
and they do not restart or retry the publication.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root


def _dead_letter_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "dead-letters"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dead_letter_log_path(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service)
    root.mkdir(parents=True, exist_ok=True)
    return root / "dead_letter_log.jsonl"


def _dead_letter_latest_path(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service)
    root.mkdir(parents=True, exist_ok=True)
    return root / "dead_letter_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_dead_letter(
    *,
    publication_id: str,
    outcome_id: str,
    outcome_ref: str | None,
    failure_id: str | None,
    failure_ref: str | None,
    attempt: int,
    max_attempts: int,
    zone_ref: str,
    topic: str,
    transport_ref: str,
    error: str | None,
    service: str = "zone-router",
) -> dict[str, Any]:
    """
    Write a dead-letter artifact for a terminal failed publication.

    Returns the dead-letter record dict with its filesystem path and log path.
    """
    dead_letter_id = str(uuid.uuid4())
    dead_letter: dict[str, Any] = {
        "version": "0.1",
        "dead_letter_id": dead_letter_id,
        "publication_id": publication_id,
        "outcome_id": outcome_id,
        "outcome_ref": outcome_ref,
        "failure_id": failure_id,
        "failure_ref": failure_ref,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "zone_ref": zone_ref,
        "topic": topic,
        "transport_ref": transport_ref,
        "error": error,
        "dead_lettered_at": _utc_now(),
        "non_claims": [
            "Dead-letter artifact is an audit record only.",
            "Dead-letter does not authorize remote mutation or remediation.",
            "Dead-letter does not restart the publication.",
        ],
    }

    artifact_path = _dead_letter_root(service) / f"{dead_letter_id}.dead-letter.json"
    dead_letter["dead_letter_ref"] = str(artifact_path)
    artifact_path.write_text(json.dumps(dead_letter, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = _dead_letter_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dead_letter, sort_keys=True) + "\n")

    latest_path = _dead_letter_latest_path(service)
    latest_path.write_text(json.dumps({"latest_dead_letter": dead_letter}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "dead_letter_id": dead_letter_id,
        "dead_letter_ref": str(artifact_path),
        "log_path": str(log_path),
        "dead_letter": dead_letter,
    }
