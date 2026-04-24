from __future__ import annotations

import json
from pathlib import Path

from zone_router.outbox import write_publication_record


def _make_plan(tmp_path: Path, *, topic: str = "zone.edge.carrier.ingested.v1") -> dict:
    return {
        "ok": True,
        "version": "0.1",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": topic,
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": str(tmp_path / "event.json"),
        "receipt_ref": str(tmp_path / "receipt.json"),
        "catalog_ref": str(tmp_path / "catalog.jsonl"),
    }


def test_write_publication_record_writes_record_and_latest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    plan = _make_plan(tmp_path)

    result = write_publication_record(plan)

    assert result["ok"] is True
    assert Path(result["record_path"]).exists()
    assert Path(result["log_path"]).exists()
    assert Path(result["latest_path"]).exists()
    assert result["record"]["status"] == "planned"
    assert result["record"]["topic"] == "zone.edge.carrier.ingested.v1"

    latest = json.loads(Path(result["latest_path"]).read_text(encoding="utf-8"))["latest_record"]
    assert latest["publication_id"] == result["record"]["publication_id"]
