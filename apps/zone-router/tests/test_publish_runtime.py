from __future__ import annotations

from pathlib import Path

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


def test_publish_publication_record_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    result = publish_publication_record(_make_record(tmp_path), transport_ref="transport://kafka/jsonl")
    assert result["ok"] is True
    assert result["outcome"]["status"] == "published"
    assert result["outcome"]["transport_kind"] == "kafka-jsonl"
    assert Path(result["outcome_path"]).exists()
    assert Path(result["transport_result"]["delivery_path"]).exists()


def test_publish_publication_record_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    result = publish_publication_record(_make_record(tmp_path), transport_ref="transport://fail/test")
    assert result["ok"] is False
    assert result["outcome"]["status"] == "failed"
    assert result["outcome"]["transport_kind"] == "fail-test"
    assert "error" in result["outcome"]
