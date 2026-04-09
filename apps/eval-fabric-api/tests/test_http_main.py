from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


def test_healthz_is_process_only():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "eval-fabric-api"
    assert payload["mode"] == "unified"


def test_readyz_success(monkeypatch):
    monkeypatch.setattr(main, "pg_health", lambda: {"ok": True})
    monkeypatch.setattr(main, "ch_health", lambda: {"ok": True})

    resp = client.get("/readyz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["postgres"]["ok"] is True
    assert payload["clickhouse"]["ok"] is True


def test_readyz_degraded(monkeypatch):
    monkeypatch.setattr(main, "pg_health", lambda: {"ok": False, "error": "postgres down"})
    monkeypatch.setattr(main, "ch_health", lambda: {"ok": True})

    resp = client.get("/readyz")
    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "degraded"
    assert payload["postgres"]["ok"] is False
    assert "error" in payload["postgres"]


def test_frontier_uses_repository(monkeypatch):
    expected = [{"subject_id": "model.semantic-stack.2026-04-05", "score": 0.782, "rank": 2}]
    monkeypatch.setattr(main.repositories, "get_frontier", lambda *args, **kwargs: expected)

    resp = client.get("/v1/frontier")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["profile_id"] == "profile.high_assurance_enterprise_agent"
    assert payload["subjects"] == expected
    assert payload["source"] == "clickhouse"


def test_dossier_uses_repository(monkeypatch):
    expected = [{"metric_definition_id": "md_denotation_accuracy", "value_scalar": 0.84}]
    monkeypatch.setattr(main.repositories, "get_model_dossier", lambda model_release_id, limit=50: expected)

    resp = client.get("/v1/models/model.semantic-stack.2026-04-05/dossier")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model_release_id"] == "model.semantic-stack.2026-04-05"
    assert payload["metrics"] == expected
    assert payload["source"] == "clickhouse"


def test_radar_uses_repository(monkeypatch):
    expected = [{"provider_id": "openai", "model_release_id": "gpt5_aug2025"}]
    monkeypatch.setattr(main.repositories, "get_competition_radar", lambda limit=50: expected)

    resp = client.get("/v1/competition/radar")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["lane"] == "high_assurance_enterprise_agent"
    assert payload["competitors"] == expected
    assert payload["source"] == "postgres"
