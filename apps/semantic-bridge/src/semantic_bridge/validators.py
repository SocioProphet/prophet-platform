from __future__ import annotations


def _validate_required(payload, required, kind, *, shape=None):
    missing = [key for key in required if key not in payload]
    result = {"ok": not missing, "kind": kind}
    if shape:
        result["shape"] = shape
    if missing:
        result["missing"] = missing
    return result


def validate_event_envelope(payload):
    canonical = ("envelope_id", "created_at", "event_type", "producer", "subject_ref", "payload_ref", "correlation_id")
    legacy = ("event_id", "event_kind", "producer", "timestamp", "payload")

    if all(key in payload for key in canonical):
        return _validate_required(payload, canonical, "event-envelope", shape="canonical")
    if all(key in payload for key in legacy):
        return _validate_required(payload, legacy, "event-envelope", shape="legacy")

    return {
        "ok": False,
        "kind": "event-envelope",
        "canonical_missing": [key for key in canonical if key not in payload],
        "legacy_missing": [key for key in legacy if key not in payload],
    }


def validate_membrane_decision(payload):
    required = ("carrier_id", "decision", "policy_ref", "timestamp")
    return _validate_required(payload, required, "membrane-decision")


def validate_zone_publication_request(payload):
    required = ("carrier_ref", "zone_ref", "event_ref", "receipt_ref", "catalog_ref")
    return _validate_required(payload, required, "zone-publication-request")


def validate_zone_publication_plan(payload):
    required = ("ok", "version", "zone_ref", "event_type", "topic", "publication_mode", "carrier_ref", "event_ref", "receipt_ref", "catalog_ref")
    return _validate_required(payload, required, "zone-publication-plan")


def validate_zone_publication_record(payload):
    required = ("version", "publication_id", "created_at", "service_ref", "status", "zone_ref", "event_type", "topic", "publication_mode", "carrier_ref", "event_ref", "receipt_ref", "catalog_ref")
    return _validate_required(payload, required, "zone-publication-record")


def validate_zone_publication_outcome(payload):
    required = ("version", "outcome_id", "publication_id", "created_at", "service_ref", "status", "transport_ref", "zone_ref", "event_type", "topic", "publication_mode", "carrier_ref", "event_ref", "receipt_ref", "catalog_ref")
    return _validate_required(payload, required, "zone-publication-outcome")
