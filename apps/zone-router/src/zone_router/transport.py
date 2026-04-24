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


def outcome_records_root(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "records"


def outcome_log_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "outcome_log.jsonl"


def latest_outcome_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "latest.json"


def ensure_transport_dirs(service: str = "zone-router") -> None:
    outcome_records_root(service).mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_publication_record(path: str | Path) -> dict[str, Any]:
    record_path = Path(path).expanduser().resolve()
    return json.loads(record_path.read_text(encoding="utf-8"))


def write_publication_outcome(
    record: dict[str, Any],
    *,
    transport_ref: str = "transport://local/jsonl",
    service_ref: str = "apps/zone-router",
    service: str = "zone-router",
    status: str = "published",
) -> dict[str, Any]:
    ensure_transport_dirs(service)
    outcome_id = str(uuid.uuid4())
    outcome = {
        "version": "0.1",
        "outcome_id": outcome_id,
        "publication_id": record["publication_id"],
        "created_at": _utc_now(),
        "service_ref": service_ref,
        "status": status,
        "transport_ref": transport_ref,
        "zone_ref": record["zone_ref"],
        "event_type": record["event_type"],
        "topic": record["topic"],
        "publication_mode": record["publication_mode"],
        "carrier_ref": record["carrier_ref"],
        "event_ref": record["event_ref"],
        "receipt_ref": record["receipt_ref"],
        "catalog_ref": record["catalog_ref"],
    }
    if record.get("topic_ref"):
        outcome["topic_ref"] = record["topic_ref"]

    outcome_path = outcome_records_root(service) / f"{outcome_id}.outcome.json"
    outcome_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = outcome_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome, sort_keys=True) + "\n")

    latest_path = latest_outcome_path(service)
    latest_path.write_text(json.dumps({"latest_outcome": outcome}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "outcome_path": str(outcome_path),
        "log_path": str(log_path),
        "latest_path": str(latest_path),
        "outcome": outcome,
    }
