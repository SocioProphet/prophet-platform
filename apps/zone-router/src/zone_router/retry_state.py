from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root


def outcome_log_path(service: str = "zone-router") -> Path:
    return publication_outbox_root(service) / "publication_outcome_log.jsonl"


def _failure_evidence_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "failure-evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


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


# Public aliases used by transport.py and tests
def load_outcomes_for_publication(publication_id: str, *, service: str = "zone-router") -> list[dict[str, Any]]:
    return read_outcomes(publication_id, service=service)


def last_outcome_for_publication(publication_id: str, *, service: str = "zone-router") -> dict[str, Any] | None:
    outcomes = read_outcomes(publication_id, service=service)
    return outcomes[-1] if outcomes else None


def next_attempt_for_publication(publication_id: str, *, service: str = "zone-router") -> int:
    return len(read_outcomes(publication_id, service=service)) + 1


def write_failure_evidence(
    record: dict[str, Any],
    outcome: dict[str, Any],
    *,
    service_ref: str = "apps/zone-router",
    service: str = "zone-router",
    previous_outcome_ref: str | None = None,
    retry_eligible: bool = True,
) -> dict[str, Any]:
    evidence_id = str(uuid.uuid4())
    evidence = {
        "version": "0.1",
        "evidence_id": evidence_id,
        "publication_id": record["publication_id"],
        "outcome_id": outcome["outcome_id"],
        "service_ref": service_ref,
        "status": "failed",
        "transport_ref": outcome.get("transport_ref"),
        "transport_kind": outcome.get("transport_kind"),
        "topic": record["topic"],
        "carrier_ref": record.get("carrier_ref"),
        "event_ref": record.get("event_ref"),
        "receipt_ref": record.get("receipt_ref"),
        "catalog_ref": record.get("catalog_ref"),
        "attempt": outcome.get("attempt", 1),
        "retry_eligible": retry_eligible,
        "previous_outcome_ref": previous_outcome_ref,
        "error": outcome.get("error"),
        "failed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    evidence_path = _failure_evidence_root(service) / f"{evidence_id}.failure-evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": False, "evidence_path": str(evidence_path), "evidence": evidence}


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
