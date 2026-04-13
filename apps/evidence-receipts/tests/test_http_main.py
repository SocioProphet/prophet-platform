from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main  # type: ignore

client = TestClient(main.app)


def _seed_eval_fabric(tmp_path: Path):
    base = tmp_path / "prophet-platform"
    (base / "payloads" / "eval-fabric-api").mkdir(parents=True, exist_ok=True)
    (base / "events" / "eval-fabric-api").mkdir(parents=True, exist_ok=True)
    (base / "receipts" / "eval-fabric-api").mkdir(parents=True, exist_ok=True)
    corr = "corr-123"
    payload_path = base / "payloads" / "eval-fabric-api" / f"{corr}.payload.json"
    event_path = base / "events" / "eval-fabric-api" / f"{corr}.event.json"
    receipt_path = base / "receipts" / "eval-fabric-api" / f"{corr}.receipt.json"
    payload_path.write_text('{"profile_id":"profile.high_assurance_enterprise_agent"}\n', encoding='utf-8')
    event_path.write_text('{"event_type":"eval.fabric.frontier.read","payload_ref":"file://' + str(payload_path.resolve()) + '","created_at":"2026-04-09T00:00:00+00:00"}\n', encoding='utf-8')
    receipt_path.write_text('{"status":"succeeded","action":"FrontierQuery","subject_ref":"profile://profile.high_assurance_enterprise_agent","created_at":"2026-04-09T00:00:00+00:00"}\n', encoding='utf-8')
    return corr


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "evidence-receipts"


def test_recent_and_detail_eval_fabric(monkeypatch, tmp_path):
    corr = _seed_eval_fabric(tmp_path)
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    recent = client.get("/v1/receipts/recent", params={"service": "eval-fabric-api", "limit": 5})
    assert recent.status_code == 200
    items = recent.json()["items"]
    assert len(items) == 1
    assert items[0]["correlation_id"] == corr
    assert items[0]["event_type"] == "eval.fabric.frontier.read"

    detail = client.get(f"/v1/receipts/eval-fabric-api/{corr}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["receipt"]["action"] == "FrontierQuery"
    assert payload["event"]["event_type"] == "eval.fabric.frontier.read"
    assert payload["payload"]["profile_id"] == "profile.high_assurance_enterprise_agent"
