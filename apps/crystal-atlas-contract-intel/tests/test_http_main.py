from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main  # type: ignore

client = TestClient(main.app)


def _seed(tmp_path: Path) -> str:
    base = tmp_path / "prophet-platform"
    (base / "payloads" / "crystal-atlas-contract-intel").mkdir(parents=True, exist_ok=True)
    (base / "events" / "crystal-atlas-contract-intel").mkdir(parents=True, exist_ok=True)
    (base / "receipts" / "crystal-atlas-contract-intel").mkdir(parents=True, exist_ok=True)
    corr = "corr-cla-001"
    payload = base / "payloads" / "crystal-atlas-contract-intel" / f"{corr}.payload.json"
    event = base / "events" / "crystal-atlas-contract-intel" / f"{corr}.event.json"
    receipt = base / "receipts" / "crystal-atlas-contract-intel" / f"{corr}.receipt.json"
    payload.write_text('{"comparison_id":"cmp-1","changed_families":["termination"]}\n', encoding='utf-8')
    event.write_text('{"event_type":"contract.clauses.compared.v0","created_at":"2026-04-14T00:00:00+00:00"}\n', encoding='utf-8')
    receipt.write_text('{"status":"succeeded","action":"CompareClauses","subject_ref":"contract://left-vs-right","created_at":"2026-04-14T00:00:00+00:00"}\n', encoding='utf-8')
    return corr


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "crystal-atlas-contract-intel"


def test_recent_and_detail(monkeypatch, tmp_path):
    corr = _seed(tmp_path)
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    recent = client.get("/v1/contract-intel/recent", params={"limit": 5})
    assert recent.status_code == 200
    items = recent.json()["items"]
    assert len(items) == 1
    assert items[0]["correlation_id"] == corr
    assert items[0]["event_type"] == "contract.clauses.compared.v0"

    detail = client.get(f"/v1/contract-intel/{corr}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["receipt"]["action"] == "CompareClauses"
    assert payload["event"]["event_type"] == "contract.clauses.compared.v0"
    assert payload["payload"]["changed_families"] == ["termination"]
