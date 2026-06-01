from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _home_fallback(suffix: str) -> Path:
    return Path.home() / suffix


def state_home() -> Path:
    value = os.environ.get("SOCIOPROFIT_STATE_HOME")
    if value:
        return Path(value)
    return _home_fallback(".local/state")


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def transport_outbox_root(service: str = "zone-router") -> Path:
    return platform_state_root() / "transport-outbox" / service


def dead_letter_records_root(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "dead-letter" / "records"


def dead_letter_log_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "dead_letter_log.jsonl"


def latest_dead_letter_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "latest_dead_letter.json"


def ensure_dead_letter_dirs(service: str = "zone-router") -> None:
    dead_letter_records_root(service).mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_dead_letter(
    record: dict[str, Any],
    outcome: dict[str, Any],
    policy: dict[str, Any],
    *,
    service_ref: str = "apps/zone-router",
    service: str = "zone-router",
    classification: str = "max-attempts-exhausted",
    previous_outcome_ref: str | None = None,
) -> dict[str, Any]:
    ensure_dead_letter_dirs(service)
    dead_letter_id = str(uuid.uuid4())
    payload = {
        "version": "0.1",
        "dead_letter_id": dead_letter_id,
        "publication_id": record["publication_id"],
        "outcome_id": outcome["outcome_id"],
        "created_at": _utc_now(),
        "service_ref": service_ref,
        "classification": classification,
        "terminal": True,
        "attempt": outcome.get("attempt", 1),
        "max_attempts": policy["max_attempts"],
        "transport_ref": outcome["transport_ref"],
        "error": outcome.get("error", "unknown transport failure"),
        "zone_ref": record["zone_ref"],
        "event_type": record["event_type"],
        "topic": record["topic"],
        "carrier_ref": record["carrier_ref"],
        "event_ref": record["event_ref"],
        "receipt_ref": record["receipt_ref"],
        "catalog_ref": record["catalog_ref"],
    }
    if previous_outcome_ref:
        payload["previous_outcome_ref"] = previous_outcome_ref

    dead_letter_path = dead_letter_records_root(service) / f"{dead_letter_id}.dead-letter.json"
    dead_letter_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = dead_letter_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")

    latest_path = latest_dead_letter_path(service)
    latest_path.write_text(json.dumps({"latest_dead_letter": payload}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "dead_letter_path": str(dead_letter_path),
        "log_path": str(log_path),
        "latest_path": str(latest_path),
        "dead_letter": payload,
    }
