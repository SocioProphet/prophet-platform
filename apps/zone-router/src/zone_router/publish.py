from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _outcomes_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "outcomes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _outcome_log_path(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service)
    root.mkdir(parents=True, exist_ok=True)
    return root / "publication_outcome_log.jsonl"


def load_publication_record(path: str | Path) -> dict[str, Any]:
    record_path = Path(path).expanduser().resolve()
    data = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected publication record object in {record_path}")
    return data


def publish_publication_record(
    *,
    record_path: str | Path,
    transport_ref: str = "transport://local/jsonl",
    service: str = "zone-router",
) -> dict[str, Any]:
    path = Path(record_path).expanduser().resolve()
    record = load_publication_record(path)
    outcome_id = str(uuid.uuid4())
    outcome = {
        "version": "0.1",
        "outcome_id": outcome_id,
        "publication_id": record["publication_id"],
        "status": "published",
        "zone_ref": record["zone_ref"],
        "topic": record["topic"],
        "transport_ref": transport_ref,
        "publication_record_ref": str(path),
        "carrier_ref": record.get("carrier_ref"),
        "event_ref": record.get("event_ref"),
        "receipt_ref": record.get("receipt_ref"),
        "catalog_ref": record.get("catalog_ref"),
        "published_at": _utc_now(),
        "error": None,
    }
    outcome_path = _outcomes_root(service) / f"{outcome_id}.publication-outcome.json"
    outcome_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = _outcome_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome, sort_keys=True) + "\n")

    return {
        "ok": True,
        "outcome_path": str(outcome_path),
        "log_path": str(log_path),
        "outcome": outcome,
    }
