from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SERVICE = "web-intel-metrics"
EVENT_TYPES = [
    "webintel.site_audit.completed.v0",
    "webintel.backlink_profile.assessed.v0",
    "webintel.ai_visibility.probed.v0",
    "webintel.serp_rank.tracked.v0",
    "webintel.content_gap.analyzed.v0",
    "webintel.scorecard.generated.v0",
]


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def _payload_dir() -> Path:
    return platform_state_root() / "payloads" / SERVICE


def _event_dir() -> Path:
    return platform_state_root() / "events" / SERVICE


def _receipt_dir() -> Path:
    return platform_state_root() / "receipts" / SERVICE


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_bundle(correlation_id: str) -> dict[str, Any] | None:
    receipt_path = _receipt_dir() / f"{correlation_id}.receipt.json"
    event_path = _event_dir() / f"{correlation_id}.event.json"
    payload_path = _payload_dir() / f"{correlation_id}.payload.json"
    if not receipt_path.exists():
        return None
    return {
        "service": SERVICE,
        "correlation_id": correlation_id,
        "receipt_ref": f"file://{receipt_path.resolve()}",
        "event_ref": f"file://{event_path.resolve()}" if event_path.exists() else None,
        "payload_ref": f"file://{payload_path.resolve()}" if payload_path.exists() else None,
        "receipt": _read_json(receipt_path),
        "event": _read_json(event_path),
        "payload": _read_json(payload_path),
    }


def _item(correlation_id: str) -> dict[str, Any] | None:
    bundle = get_bundle(correlation_id)
    if bundle is None:
        return None
    receipt = bundle.get("receipt") or {}
    event = bundle.get("event") or {}
    payload = bundle.get("payload") or {}
    return {
        "correlation_id": correlation_id,
        "created_at": receipt.get("created_at") or event.get("created_at"),
        "action": receipt.get("action"),
        "status": receipt.get("status"),
        "event_type": event.get("event_type"),
        "subject": payload.get("subject") or receipt.get("subject_ref") or event.get("subject_ref"),
        "relation": payload.get("relation"),
        "overall_epistemic_level": payload.get("overall_epistemic_level") or payload.get("epistemic_level"),
    }


def list_recent(limit: int = 20, subject: str | None = None) -> list[dict[str, Any]]:
    if not _receipt_dir().exists():
        return []
    files = sorted(_receipt_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    items: list[dict[str, Any]] = []
    for path in files:
        correlation_id = path.name.removesuffix(".receipt.json")
        item = _item(correlation_id)
        if item is None:
            continue
        if subject is not None and item.get("subject") != subject:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items
