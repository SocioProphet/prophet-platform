from __future__ import annotations

import json
from pathlib import Path

from zone_router.planner import plan_publication_request


def _make_request(tmp_path: Path, *, topic_ref: str | None = None) -> dict:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"event_type": "carrier.ingested"}), encoding="utf-8")
    request = {
        "carrier_ref": "carrier://sha256/example",
        "zone_ref": "zone://edge",
        "event_ref": str(event_path),
        "receipt_ref": str(tmp_path / "receipt.json"),
        "catalog_ref": str(tmp_path / "catalog.jsonl"),
    }
    if topic_ref:
        request["topic_ref"] = topic_ref
    return request


def test_plan_publication_request_resolves_topic_from_event(tmp_path: Path) -> None:
    request = _make_request(tmp_path)
    plan = plan_publication_request(request)
    assert plan["ok"] is True
    assert plan["event_type"] == "carrier.ingested"
    assert plan["topic"] == "zone.edge.carrier.ingested.v1"
    assert plan["publication_mode"] == "resolved"


def test_plan_publication_request_keeps_explicit_topic(tmp_path: Path) -> None:
    request = _make_request(tmp_path, topic_ref="zone.edge.custom.v1")
    plan = plan_publication_request(request)
    assert plan["ok"] is True
    assert plan["topic"] == "zone.edge.custom.v1"
    assert plan["publication_mode"] == "explicit"
