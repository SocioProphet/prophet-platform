from __future__ import annotations

import json
from pathlib import Path

from zone_router.main import main


def test_plan_request_cli_outputs_plan(tmp_path: Path, capsys) -> None:
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

    rc = main(["plan-request", "--path", str(request_path)])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["topic"] == "zone.edge.carrier.ingested.v1"
