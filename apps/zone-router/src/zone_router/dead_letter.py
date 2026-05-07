from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dead_letter_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "dead-letter"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dead_letter_log_path(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service)
    root.mkdir(parents=True, exist_ok=True)
    return root / "dead_letter_log.jsonl"


def write_dead_letter(
    *,
    record: dict[str, Any],
    outcome: dict[str, Any],
    policy: dict[str, Any],
    service: str = "zone-router",
    classification: str = "max-attempts-exhausted",
) -> dict[str, Any]:
    dead_letter_id = str(uuid.uuid4())
    payload = {
        "version": "0.1",
        "dead_letter_id": dead_letter_id,
        "publication_id": record["publication_id"],
        "outcome_id": outcome["outcome_id"],
        "created_at": _utc_now(),
        "classification": classification,
        "terminal": True,
        "attempt": outcome["attempt"],
        "max_attempts": policy["max_attempts"],
        "transport_ref": outcome["transport_ref"],
        "transport_kind": outcome["transport_kind"],
        "zone_ref": outcome["zone_ref"],
        "topic": outcome["topic"],
        "publication_record_ref": outcome["publication_record_ref"],
        "carrier_ref": outcome.get("carrier_ref"),
        "event_ref": outcome.get("event_ref"),
        "receipt_ref": outcome.get("receipt_ref"),
        "catalog_ref": outcome.get("catalog_ref"),
        "error": outcome.get("error"),
    }
    if outcome.get("previous_outcome_ref"):
        payload["previous_outcome_ref"] = outcome["previous_outcome_ref"]

    path = _dead_letter_root(service) / f"{dead_letter_id}.dead-letter.json"
    payload["dead_letter_ref"] = str(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = _dead_letter_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")

    return {
        "ok": True,
        "dead_letter_path": str(path),
        "log_path": str(log_path),
        "dead_letter": payload,
    }
