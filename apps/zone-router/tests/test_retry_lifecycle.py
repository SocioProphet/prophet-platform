from __future__ import annotations

from pathlib import Path

from zone_router.retry_state import load_outcomes_for_publication
from zone_router.transport import publish_publication_record


def _make_record(tmp_path: Path, *, topic: str = "zone.edge.carrier.ingested.v1") -> dict:
    return {
        "version": "0.1",
        "publication_id": "pub-001",
        "created_at": "2026-04-20T00:00:00Z",
        "service_ref": "apps/zone-router",
        "status": "planned",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": topic,
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": str(tmp_path / "event.json"),
        "receipt_ref": str(tmp_path / "receipt.json"),
        "catalog_ref": str(tmp_path / "catalog.jsonl"),
    }


def test_publish_retry_lifecycle_records_failure_then_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    record = _make_record(tmp_path)

    first = publish_publication_record(record, transport_ref="transport://fail/test")
    assert first["ok"] is False
    assert first["outcome"]["status"] == "failed"
    assert first["outcome"]["attempt"] == 1
    assert first["outcome"]["retry_eligible"] is True
    assert Path(first["failure_evidence"]["evidence_path"]).exists()

    second = publish_publication_record(record, transport_ref="transport://local/jsonl")
    assert second["ok"] is True
    assert second["outcome"]["status"] == "published"
    assert second["outcome"]["attempt"] == 2
    assert second["outcome"]["retry_eligible"] is False
    assert second["outcome"]["previous_outcome_ref"] == first["outcome"]["outcome_id"]

    outcomes = load_outcomes_for_publication("pub-001")
    assert [item["attempt"] for item in outcomes] == [1, 2]
