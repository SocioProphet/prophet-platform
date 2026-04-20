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


def publication_outbox_root(service: str = "zone-router") -> Path:
    return platform_state_root() / "publication-outbox" / service


def publication_records_root(service: str = "zone-router") -> Path:
    return publication_outbox_root(service) / "records"


def publication_log_path(service: str = "zone-router") -> Path:
    return publication_outbox_root(service) / "publication_log.jsonl"


def latest_record_path(service: str = "zone-router") -> Path:
    return publication_outbox_root(service) / "latest.json"


def ensure_outbox_dirs(service: str = "zone-router") -> None:
    publication_records_root(service).mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_publication_record(plan: dict[str, Any], *, service_ref: str = "apps/zone-router", service: str = "zone-router") -> dict[str, Any]:
    ensure_outbox_dirs(service)
    publication_id = str(uuid.uuid4())
    record = {
        "version": "0.1",
        "publication_id": publication_id,
        "created_at": _utc_now(),
        "service_ref": service_ref,
        "status": "planned",
        "zone_ref": plan["zone_ref"],
        "event_type": plan["event_type"],
        "topic": plan["topic"],
        "publication_mode": plan["publication_mode"],
        "carrier_ref": plan["carrier_ref"],
        "event_ref": plan["event_ref"],
        "receipt_ref": plan["receipt_ref"],
        "catalog_ref": plan["catalog_ref"],
    }
    if plan.get("topic_ref"):
        record["topic_ref"] = plan["topic_ref"]

    record_path = publication_records_root(service) / f"{publication_id}.publication.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = publication_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")

    latest_path = latest_record_path(service)
    latest_path.write_text(json.dumps({"latest_record": record}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "record_path": str(record_path),
        "log_path": str(log_path),
        "latest_path": str(latest_path),
        "record": record,
    }
