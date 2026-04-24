from __future__ import annotations

import json
from pathlib import Path

from zone_router.main import main


def test_publish_record_cli_outputs_outcome(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    record_path = tmp_path / "publication_record.json"
    record_path.write_text(
        json.dumps(
            {
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
                "event_ref": str(tmp_path / "event.json"),
                "receipt_ref": str(tmp_path / "receipt.json"),
                "catalog_ref": str(tmp_path / "catalog.jsonl"),
            }
        ),
        encoding="utf-8",
    )

    rc = main(["publish-record", "--path", str(record_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["outcome"]["status"] == "published"
    assert payload["outcome"]["transport_ref"] == "transport://local/jsonl"
    assert payload["semantic_validation"]["record"]["ok"] is True
