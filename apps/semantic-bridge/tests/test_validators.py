from __future__ import annotations

from semantic_bridge.validators import (
    validate_event_envelope,
    validate_membrane_decision,
    validate_zone_publication_outcome,
    validate_zone_publication_plan,
    validate_zone_publication_record,
    validate_zone_publication_request,
)


def test_validate_event_envelope_accepts_canonical_shape() -> None:
    payload = {
        "envelope_id": "env-001",
        "created_at": "2026-04-20T00:00:00Z",
        "event_type": "carrier.ingested",
        "producer": "apps/lampstand",
        "subject_ref": "carrier://sha256/example",
        "payload_ref": "file:///tmp/payload.json",
        "correlation_id": "corr-001",
    }
    result = validate_event_envelope(payload)
    assert result["ok"] is True
    assert result["shape"] == "canonical"


def test_validate_event_envelope_accepts_legacy_shape() -> None:
    payload = {
        "event_id": "evt-001",
        "event_kind": "carrier.ingested",
        "producer": "apps/lampstand",
        "timestamp": "2026-04-20T00:00:00Z",
        "payload": {},
    }
    result = validate_event_envelope(payload)
    assert result["ok"] is True
    assert result["shape"] == "legacy"


def test_validate_membrane_decision_accepts_required_shape() -> None:
    payload = {
        "carrier_id": "carrier://sha256/example",
        "decision": "admit",
        "policy_ref": "policy://edge/default",
        "timestamp": "2026-04-20T00:00:00Z",
    }
    result = validate_membrane_decision(payload)
    assert result["ok"] is True


def test_validate_zone_publication_request_accepts_required_shape() -> None:
    payload = {
        "carrier_ref": "carrier://sha256/example",
        "zone_ref": "zone://edge",
        "event_ref": "/tmp/event.json",
        "receipt_ref": "/tmp/receipt.json",
        "catalog_ref": "/tmp/catalog.jsonl",
    }
    result = validate_zone_publication_request(payload)
    assert result["ok"] is True


def test_validate_zone_publication_plan_accepts_required_shape() -> None:
    payload = {
        "ok": True,
        "version": "0.1",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": "zone.edge.carrier.ingested.v1",
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": "/tmp/event.json",
        "receipt_ref": "/tmp/receipt.json",
        "catalog_ref": "/tmp/catalog.jsonl",
    }
    result = validate_zone_publication_plan(payload)
    assert result["ok"] is True


def test_validate_zone_publication_record_accepts_required_shape() -> None:
    payload = {
        "version": "0.1",
        "publication_id": "pub-001",
        "created_at": "2026-04-20T00:00:00Z",
        "service_ref": "apps/zone-router",
        "status": "planned",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": "zone.edge.carrier.ingested.v1",
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": "/tmp/event.json",
        "receipt_ref": "/tmp/receipt.json",
        "catalog_ref": "/tmp/catalog.jsonl",
    }
    result = validate_zone_publication_record(payload)
    assert result["ok"] is True


def test_validate_zone_publication_outcome_accepts_required_shape() -> None:
    payload = {
        "version": "0.1",
        "outcome_id": "out-001",
        "publication_id": "pub-001",
        "created_at": "2026-04-20T00:00:00Z",
        "service_ref": "apps/zone-router",
        "status": "published",
        "transport_ref": "transport://local/jsonl",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": "zone.edge.carrier.ingested.v1",
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": "/tmp/event.json",
        "receipt_ref": "/tmp/receipt.json",
        "catalog_ref": "/tmp/catalog.jsonl",
    }
    result = validate_zone_publication_outcome(payload)
    assert result["ok"] is True
