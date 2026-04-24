from __future__ import annotations

import json
from pathlib import Path

from .resolver import resolve_topic

_PLAN_VERSION = "1.0"


def load_publication_request(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def plan_publication_request(request):
    event_ref = request.get("event_ref", "")
    event_type = "unknown"
    try:
        event_data = json.loads(Path(event_ref).read_text(encoding="utf-8"))
        event_type = event_data.get("event_type", "unknown")
    except Exception:
        pass

    zone_ref = request.get("zone_ref", "zone://edge")
    topic = resolve_topic(zone_ref, event_type)

    return {
        "ok": True,
        "version": _PLAN_VERSION,
        "zone_ref": zone_ref,
        "event_type": event_type,
        "topic": topic,
        "publication_mode": "resolved",
        "carrier_ref": request.get("carrier_ref", ""),
        "event_ref": event_ref,
        "receipt_ref": request.get("receipt_ref", ""),
        "catalog_ref": request.get("catalog_ref", ""),
    }
