"""Catalog operational plane — capture layer.

The Catalog Gateway keeps a record of what it does. Every resolve / DCAT emission is
crystallized as a `catalog.*.v0` event (contracts/crystal-atlas/events/) and written
into the SAME shared file-state that evidence-receipts / crystal-atlas-contract-intel
already read — so catalog operations are observable and queryable with zero new store.

Capture is best-effort: an emit failure must never break a read. Toggle with
CATALOG_OPS_CAPTURE (default on). Downstream: a scheduled readout folds these into
catalog KPIs (hit/miss, hot assets, stale sources, DCAT coverage), and SLOs gate them.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import SERVICE, state_home

PRODUCER = "catalog-gateway"


def _enabled() -> bool:
    return os.getenv("CATALOG_OPS_CAPTURE", "true").lower() != "false"


def _events_dir() -> Path:
    return state_home() / "prophet-platform" / "events" / SERVICE


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(event_type: str, record: dict[str, Any]) -> str | None:
    """Write one crystallized operational event. Best-effort: returns the event_id, or
    None if capture is off or the write fails (never raises into the caller)."""
    if not _enabled():
        return None
    try:
        event_id = record.get("event_id") or f"ce_{uuid.uuid4().hex[:16]}"
        record.setdefault("event_id", event_id)
        record.setdefault("emitted_at", _now())
        record.setdefault("producer", PRODUCER)
        d = _events_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{event_id}.event.json").write_text(
            json.dumps({"event_type": event_type, "event": record}, indent=2), encoding="utf-8"
        )
        return event_id
    except OSError:
        return None


def record_resolved(kind: str, entry_id: str, hit: bool, *, requester: str | None = None,
                    latency_ms: float | None = None) -> str | None:
    return emit("catalog.resolved.v0", {
        "kind": kind, "entry_id": entry_id, "hit": hit,
        "requester": requester, "latency_ms": latency_ms,
    })


def record_dcat_emitted(asset_id: str, access_rights: str, *, distribution_class: str | None = None,
                        requester: str | None = None) -> str | None:
    return emit("catalog.dcat.emitted.v0", {
        "asset_id": asset_id, "access_rights": access_rights,
        "distribution_class": distribution_class, "requester": requester,
    })
