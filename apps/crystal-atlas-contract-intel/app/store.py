from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SERVICE = "crystal-atlas-contract-intel"
EVENT_TYPES = [
    "contract.clauses.compared.v0",
    "procurement.substitution.recommended.v0",
    "entitlement.adjacency.inferred.v0",
    "diligence.risk.pack.generated.v0",
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


def list_recent(limit: int = 20) -> list[dict[str, Any]]:
    if not _receipt_dir().exists():
        return []
    files = sorted(_receipt_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    items: list[dict[str, Any]] = []
    for path in files[:limit]:
        correlation_id = path.name.removesuffix(".receipt.json")
        bundle = get_bundle(correlation_id)
        if bundle is None:
            continue
        receipt = bundle.get("receipt") or {}
        event = bundle.get("event") or {}
        items.append({
            "correlation_id": correlation_id,
            "created_at": receipt.get("created_at") or event.get("created_at"),
            "action": receipt.get("action"),
            "status": receipt.get("status"),
            "event_type": event.get("event_type"),
            "subject_ref": receipt.get("subject_ref") or event.get("subject_ref"),
        })
    return items
