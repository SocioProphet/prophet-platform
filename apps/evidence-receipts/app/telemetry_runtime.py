from __future__ import annotations

from typing import Any


def load_manifest(event_type: str) -> dict[str, Any]:
    return {"event_type": event_type}


def reduce_event(event_type: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    subject = payload.get("subject_ref")
    if subject is None:
        subject = event_type
    return {
        "event": event_type,
        "fields": dict(payload),
        "action": "ALLOW",
        "subject_ref": str(subject),
    }


def emit_event_bundle(service: str, event_type: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    outcome = reduce_event(event_type, payload, **kwargs)
    return {"service": service, "outcome": outcome, "payload": dict(payload)}
