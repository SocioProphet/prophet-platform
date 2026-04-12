from __future__ import annotations


def validate_event_envelope(payload):
    ok = True
    for key in ("event_id", "event_kind", "producer", "timestamp", "payload"):
        if key not in payload:
            ok = False
    return {"ok": ok, "kind": "event-envelope"}


def validate_membrane_decision(payload):
    ok = True
    for key in ("carrier_id", "decision", "policy_ref", "timestamp"):
        if key not in payload:
            ok = False
    return {"ok": ok, "kind": "membrane-decision"}
