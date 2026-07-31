from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main  # type: ignore

client = TestClient(main.app)


def _seed(tmp_path: Path, subject: str, corr: str) -> None:
    base = tmp_path / "prophet-platform"
    for kind in ("payloads", "events", "receipts"):
        (base / kind / "web-intel-metrics").mkdir(parents=True, exist_ok=True)
    payload = base / "payloads" / "web-intel-metrics" / f"{corr}.payload.json"
    event = base / "events" / "web-intel-metrics" / f"{corr}.event.json"
    receipt = base / "receipts" / "web-intel-metrics" / f"{corr}.receipt.json"
    payload.write_text(
        '{"subject":"' + subject + '","relation":"self","overall_epistemic_level":"empirical",'
        '"headline":{"site_health_score":61.5}}\n',
        encoding="utf-8",
    )
    event.write_text(
        '{"event_type":"webintel.scorecard.generated.v0","created_at":"2026-07-31T00:00:00+00:00","subject_ref":"'
        + subject + '"}\n',
        encoding="utf-8",
    )
    receipt.write_text(
        '{"status":"succeeded","action":"GenerateWebIntelScorecard","subject_ref":"' + subject
        + '","created_at":"2026-07-31T00:00:00+00:00"}\n',
        encoding="utf-8",
    )


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "web-intel-metrics"


def test_event_types():
    resp = client.get("/v1/web-intel/event-types")
    assert resp.status_code == 200
    types = resp.json()["event_types"]
    assert "webintel.scorecard.generated.v0" in types
    assert "webintel.ai_visibility.probed.v0" in types


def test_recent_by_subject_and_detail(monkeypatch, tmp_path):
    _seed(tmp_path, "socioprophet.com", "wi-self-1")
    _seed(tmp_path, "a-competitor.example", "wi-comp-1")
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    recent = client.get("/v1/web-intel/recent", params={"limit": 10})
    assert recent.status_code == 200
    assert len(recent.json()["items"]) == 2

    # Symmetric: query a competitor's subject just like our own.
    comp = client.get("/v1/web-intel/by-subject/a-competitor.example")
    assert comp.status_code == 200
    comp_items = comp.json()["items"]
    assert len(comp_items) == 1
    assert comp_items[0]["subject"] == "a-competitor.example"

    detail = client.get("/v1/web-intel/wi-self-1")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["payload"]["subject"] == "socioprophet.com"
    assert payload["event"]["event_type"] == "webintel.scorecard.generated.v0"


def test_detail_404():
    assert client.get("/v1/web-intel/does-not-exist").status_code == 404
