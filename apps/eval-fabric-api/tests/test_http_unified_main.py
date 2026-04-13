from __future__ import annotations

from fastapi.testclient import TestClient

import app.unified_main as unified_main

client = TestClient(unified_main.app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "eval-fabric-api"


def test_readyz_success(monkeypatch):
    monkeypatch.setattr(unified_main.db, "pg_health", lambda: {"ok": True})
    monkeypatch.setattr(unified_main.db, "ch_health", lambda: {"ok": True})

    resp = client.get("/readyz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["postgres"]["ok"] is True
    assert payload["clickhouse"]["ok"] is True


def test_readyz_degraded(monkeypatch):
    monkeypatch.setattr(unified_main.db, "pg_health", lambda: {"ok": False, "error": "postgres down"})
    monkeypatch.setattr(unified_main.db, "ch_health", lambda: {"ok": True})

    resp = client.get("/readyz")
    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "degraded"
    assert payload["postgres"]["ok"] is False


def test_frontier_provenance_uses_repository(monkeypatch):
    expected = [{"model_release_id": "model.semantic-stack.2026-04-05", "metric_fact_count": 2}]
    monkeypatch.setattr(unified_main.intelligence_repositories, "get_frontier_provenance", lambda limit=50: expected)

    resp = client.get("/v1/frontier/provenance?limit=7")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["subjects"] == expected
    assert payload["source"] == "clickhouse"


def test_reproduced_vs_claimed_uses_repository(monkeypatch):
    expected = [{"provider_id": "openai", "coverage_state": "claimed_only"}]
    monkeypatch.setattr(unified_main.intelligence_repositories, "get_reproduced_vs_claimed", lambda limit=50: expected)

    resp = client.get("/v1/competition/reproduced-vs-claimed?limit=9")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"] == expected
    assert payload["source"] == "postgres"
