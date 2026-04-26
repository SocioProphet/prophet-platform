from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root


def outcome_log_path(service: str = "zone-router") -> Path:
    return publication_outbox_root(service) / "publication_outcome_log.jsonl"


def read_outcomes(publication_id: str, *, service: str = "zone-router") -> list[dict[str, Any]]:
    path = outcome_log_path(service)
    if not path.exists():
        return []
    outcomes: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if isinstance(data, dict) and data.get("publication_id") == publication_id:
            outcomes.append(data)
    return outcomes


def next_attempt_state(publication_id: str, *, service: str = "zone-router") -> dict[str, Any]:
    outcomes = read_outcomes(publication_id, service=service)
    previous = outcomes[-1] if outcomes else None
    return {
        "attempt": len(outcomes) + 1,
        "previous_outcome_id": previous.get("outcome_id") if previous else None,
        "previous_outcome_status": previous.get("status") if previous else None,
        "previous_outcome_ref": previous.get("outcome_ref") if previous else None,
        "retry_after_failure": bool(previous and previous.get("status") == "failed"),
    }


def retry_eligible(outcome: dict[str, Any]) -> bool:
    return outcome.get("status") == "failed"
