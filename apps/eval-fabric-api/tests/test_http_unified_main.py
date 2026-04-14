from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as canonical_main
import app.unified_main as unified_main

client = TestClient(unified_main.app)


def test_unified_main_wrapper_reexports_canonical_app():
    assert unified_main.app is canonical_main.app


def test_unified_main_wrapper_exposes_canonical_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "eval-fabric-api"
    assert payload["mode"] == "canonical"


def test_unified_main_wrapper_exposes_frontier_provenance_route(monkeypatch):
    expected = [{"model_release_id": "model.semantic-stack.2026-04-05", "metric_fact_count": 2}]
    monkeypatch.setattr(canonical_main.intelligence_repositories, "get_frontier_provenance", lambda limit=50: expected)
    resp = client.get("/v1/frontier/provenance?limit=7")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["subjects"] == expected
    assert payload["source"] == "clickhouse"
