from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import catalog_root, ensure_service_dirs


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _catalog_file(service: str = "lampstand") -> Path:
    ensure_service_dirs(service)
    return catalog_root(service) / "receipt_catalog.jsonl"


def _latest_file(service: str = "lampstand") -> Path:
    ensure_service_dirs(service)
    return catalog_root(service) / "latest.json"


def make_entry(
    *,
    service_ref: str,
    event_type: str,
    subject_ref: str,
    envelope_ref: str,
    receipt_ref: str,
    payload_ref: str,
    status: str,
    scope_ref: str | None = None,
    correlation_id: str | None = None,
    classifiers: list[str] | None = None,
) -> dict[str, Any]:
    entry = {
        "version": "0.1",
        "entry_id": str(uuid.uuid4()),
        "created_at": _utc_now(),
        "service_ref": service_ref,
        "event_type": event_type,
        "status": status,
        "subject_ref": subject_ref,
        "envelope_ref": envelope_ref,
        "receipt_ref": receipt_ref,
        "payload_ref": payload_ref,
    }
    if scope_ref:
        entry["scope_ref"] = scope_ref
    if correlation_id:
        entry["correlation_id"] = correlation_id
    if classifiers:
        entry["classifiers"] = classifiers
    return entry


def append_entry(entry: dict[str, Any], *, service: str = "lampstand") -> Path:
    path = _catalog_file(service)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    _latest_file(service).write_text(json.dumps({"latest_entry": entry}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_entries(*, service: str = "lampstand", limit: int = 20, event_type_prefix: str | None = None) -> list[dict[str, Any]]:
    path = _catalog_file(service)
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if event_type_prefix and not obj.get("event_type", "").startswith(event_type_prefix):
            continue
        items.append(obj)
    if limit > 0:
        items = items[-limit:]
    return list(reversed(items))
