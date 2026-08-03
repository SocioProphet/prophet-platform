from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)
FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_agent_eval_metrics_route_healthy_returns_200_and_passes_gate():
    resp = client.post("/v1/agent-eval/metrics", json=_load("agent_eval_healthy_0001.json"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["anomalyStatus"] == "normal"
    assert body["gate"]["passed"] is True
    assert body["gate"]["breaches"] == []
    assert body["contract_version"] == "0.1.0"


def test_agent_eval_metrics_route_anomalous_fails_closed_with_422():
    resp = client.post("/v1/agent-eval/metrics", json=_load("agent_eval_anomalous_0001.json"))
    assert resp.status_code == 422
    body = resp.json()
    assert body["metrics"]["anomalyStatus"] == "anomalous"
    assert body["gate"]["passed"] is False
    assert body["gate"]["breaches"]
