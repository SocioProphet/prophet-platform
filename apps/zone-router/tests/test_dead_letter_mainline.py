from __future__ import annotations

from pathlib import Path

from zone_router.outbox import write_publication_record
from zone_router.publish import publish_publication_record


def _plan(tmp_path: Path) -> dict:
    return {
        "ok": True,
        "version": "0.1",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": "zone.edge.carrier.ingested.v1",
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": str(tmp_path / "event.json"),
        "receipt_ref": str(tmp_path / "receipt.json"),
        "catalog_ref": str(tmp_path / "catalog.jsonl"),
    }


def test_publish_terminal_failure_writes_dead_letter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    created = write_publication_record(_plan(tmp_path))
    record_path = Path(created["record_path"])
    record = created["record"]
    record["retry_policy"] = {
        "version": "0.1",
        "max_attempts": 2,
        "backoff_seconds": 5,
        "strategy": "fixed",
        "dead_letter_on_terminal": True,
    }
    record_path.write_text(__import__("json").dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    first = publish_publication_record(record_path=record_path, transport_ref="transport://fail/test")
    assert first["ok"] is False
    assert first["outcome"]["attempt"] == 1
    assert first["outcome"]["retry_eligible"] is True
    assert first["outcome"]["terminal"] is False
    assert first["outcome"]["next_retry_not_before"] is not None
    assert "dead_letter" not in first

    second = publish_publication_record(record_path=record_path, transport_ref="transport://fail/test")
    assert second["ok"] is False
    assert second["outcome"]["attempt"] == 2
    assert second["outcome"]["retry_eligible"] is False
    assert second["outcome"]["terminal"] is True
    assert second["outcome"]["next_retry_not_before"] is None
    assert second["dead_letter"]["ok"] is True
    assert Path(second["dead_letter"]["dead_letter_path"]).exists()
