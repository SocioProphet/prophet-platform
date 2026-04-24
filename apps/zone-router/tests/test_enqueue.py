from __future__ import annotations

import json
from pathlib import Path

from zone_router.main import main


def test_enqueue_request_cli_outputs_record(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    event_path = tmp_path / "event.json"
    request_path = tmp_path / "publication_request.json"
    event_path.write_text(json.dumps({"event_type": "carrier.ingested"}), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "carrier_ref": "carrier://sha256/example",
                "zone_ref": "zone://edge",
                "event_ref": str(event_path),
                "receipt_ref": str(tmp_path / "receipt.json"),
                "catalog_ref": str(tmp_path / "catalog.jsonl"),
            }
        ),
        encoding="utf-8",
    )

    rc = main(["enqueue-request", "--path", str(request_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["record"]["status"] == "planned"
    assert payload["record"]["topic"] == "zone.edge.carrier.ingested.v1"
