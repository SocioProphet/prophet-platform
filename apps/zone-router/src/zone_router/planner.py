from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .resolver import resolve_topic

REQUIRED_REQUEST_KEYS = ("carrier_ref", "zone_ref", "event_ref", "receipt_ref", "catalog_ref")


def _coerce_path(ref: str) -> Path:
    value = str(ref)
    if value.startswith("file://"):
        value = value[len("file://"):]
    return Path(value).expanduser().resolve()


def load_publication_request(path: str | Path) -> dict[str, Any]:
    request_path = Path(path).expanduser().resolve()
    return json.loads(request_path.read_text(encoding="utf-8"))


def load_event_envelope(event_ref: str) -> dict[str, Any]:
    event_path = _coerce_path(event_ref)
    return json.loads(event_path.read_text(encoding="utf-8"))


def validate_publication_request(request: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_REQUEST_KEYS if key not in request]
    return {"ok": not missing, "missing": missing}


def derive_event_type(request: dict[str, Any]) -> str:
    explicit = request.get("event_type")
    if explicit:
        return str(explicit)
    event = load_event_envelope(request["event_ref"])
    derived = event.get("event_type") or event.get("event_kind") or "unknown"
    return str(derived)


def plan_publication_request(request: dict[str, Any]) -> dict[str, Any]:
    validation = validate_publication_request(request)
    if not validation["ok"]:
        return {"ok": False, "missing": validation["missing"]}

    event_type = derive_event_type(request)
    topic = request.get("topic_ref") or resolve_topic(request["zone_ref"], event_type)
    mode = "explicit" if request.get("topic_ref") else "resolved"

    plan = {
        "ok": True,
        "version": "0.1",
        "zone_ref": request["zone_ref"],
        "event_type": event_type,
        "topic": topic,
        "publication_mode": mode,
        "carrier_ref": request["carrier_ref"],
        "event_ref": request["event_ref"],
        "receipt_ref": request["receipt_ref"],
        "catalog_ref": request["catalog_ref"],
    }
    if request.get("topic_ref"):
        plan["topic_ref"] = request["topic_ref"]
    return plan
