from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Layout:
    service: str
    payload_dir: Path
    event_dir: Path
    receipt_dir: Path
    catalog_file: Path | None


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def _service_first_layout(service: str) -> Layout:
    root = platform_state_root() / service
    return Layout(
        service=service,
        payload_dir=root / "payloads",
        event_dir=root / "events",
        receipt_dir=root / "receipts",
        catalog_file=root / "catalog" / "receipt_catalog.jsonl",
    )


def _type_first_layout(service: str) -> Layout:
    root = platform_state_root()
    return Layout(
        service=service,
        payload_dir=root / "payloads" / service,
        event_dir=root / "events" / service,
        receipt_dir=root / "receipts" / service,
        catalog_file=root / "catalog" / service / "receipt_catalog.jsonl",
    )


def _layout_score(layout: Layout) -> int:
    score = 0
    for p in [layout.payload_dir, layout.event_dir, layout.receipt_dir]:
        if p.exists():
            score += 1
    if layout.catalog_file and layout.catalog_file.exists():
        score += 1
    return score


def resolve_layout(service: str) -> Layout:
    candidates = [_service_first_layout(service), _type_first_layout(service)]
    scored = sorted(candidates, key=_layout_score, reverse=True)
    if _layout_score(scored[0]) > 0:
        return scored[0]
    # default to service-first for new producers; it matches eval-fabric's current path
    return _service_first_layout(service)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_payload_path(layout: Layout, correlation_id: str) -> Path | None:
    direct = layout.payload_dir / f"{correlation_id}.payload.json"
    if direct.exists():
        return direct
    matches = sorted(layout.payload_dir.glob(f"{correlation_id}*.json"))
    return matches[0] if matches else None


def _candidate_event_path(layout: Layout, correlation_id: str) -> Path | None:
    direct = layout.event_dir / f"{correlation_id}.event.json"
    if direct.exists():
        return direct
    matches = sorted(layout.event_dir.glob(f"{correlation_id}*.json"))
    return matches[0] if matches else None


def _candidate_receipt_path(layout: Layout, correlation_id: str) -> Path | None:
    direct = layout.receipt_dir / f"{correlation_id}.receipt.json"
    if direct.exists():
        return direct
    matches = sorted(layout.receipt_dir.glob(f"{correlation_id}*.json"))
    return matches[0] if matches else None


def _infer_payload_ref(layout: Layout, correlation_id: str, event: dict[str, Any] | None, catalog_entry: dict[str, Any] | None) -> str | None:
    if event and isinstance(event.get("payload_ref"), str):
        return event["payload_ref"]
    if catalog_entry and isinstance(catalog_entry.get("payload_ref"), str):
        return catalog_entry["payload_ref"]
    payload_path = _candidate_payload_path(layout, correlation_id)
    if payload_path is not None:
        return f"file://{payload_path.resolve()}"
    return None


def read_catalog_entries(service: str, limit: int = 20) -> list[dict[str, Any]]:
    layout = resolve_layout(service)
    path = layout.catalog_file
    if path is None or not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    if limit > 0:
        items = items[-limit:]
    return list(reversed(items))


def _catalog_entry_by_correlation(service: str, correlation_id: str) -> dict[str, Any] | None:
    for item in read_catalog_entries(service=service, limit=500):
        if item.get("correlation_id") == correlation_id:
            return item
    return None


def get_bundle(service: str, correlation_id: str) -> dict[str, Any] | None:
    layout = resolve_layout(service)
    receipt_path = _candidate_receipt_path(layout, correlation_id)
    if receipt_path is None:
        return None
    event_path = _candidate_event_path(layout, correlation_id)
    catalog_entry = _catalog_entry_by_correlation(service, correlation_id)

    receipt = _read_json(receipt_path)
    event = _read_json(event_path) if event_path else None
    payload_ref = _infer_payload_ref(layout, correlation_id, event, catalog_entry)
    payload = None
    if payload_ref and payload_ref.startswith("file://"):
        payload = _read_json(Path(payload_ref.removeprefix("file://")))

    return {
        "service": service,
        "correlation_id": correlation_id,
        "receipt_ref": f"file://{receipt_path.resolve()}",
        "event_ref": f"file://{event_path.resolve()}" if event_path else None,
        "payload_ref": payload_ref,
        "receipt": receipt,
        "event": event,
        "payload": payload,
        "catalog_entry": catalog_entry,
    }


def list_recent_bundles(service: str, limit: int = 20) -> list[dict[str, Any]]:
    layout = resolve_layout(service)
    if not layout.receipt_dir.exists():
        return []
    files = sorted(layout.receipt_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    items: list[dict[str, Any]] = []
    for path in files[:limit]:
        stem = path.name
        if stem.endswith(".receipt.json"):
            correlation_id = stem[: -len(".receipt.json")]
        else:
            correlation_id = path.stem
        bundle = get_bundle(service=service, correlation_id=correlation_id)
        if bundle is None:
            continue
        receipt = bundle.get("receipt") or {}
        event = bundle.get("event") or {}
        items.append({
            "service": service,
            "correlation_id": correlation_id,
            "created_at": receipt.get("created_at") or event.get("created_at"),
            "status": receipt.get("status"),
            "action": receipt.get("action"),
            "event_type": event.get("event_type"),
            "subject_ref": receipt.get("subject_ref") or event.get("subject_ref"),
            "receipt_ref": bundle.get("receipt_ref"),
            "event_ref": bundle.get("event_ref"),
            "payload_ref": bundle.get("payload_ref"),
        })
    return items


def list_services() -> list[str]:
    root = platform_state_root()
    services = set()
    # service-first layout
    for child in root.iterdir() if root.exists() else []:
        if not child.is_dir():
            continue
        if (child / "receipts").exists() or (child / "events").exists() or (child / "payloads").exists():
            services.add(child.name)
    # type-first layout
    for kind in ["payloads", "events", "receipts", "catalog"]:
        kind_dir = root / kind
        if not kind_dir.exists():
            continue
        for child in kind_dir.iterdir():
            if child.is_dir():
                services.add(child.name)
    return sorted(services)
