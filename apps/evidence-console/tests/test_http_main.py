from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "evidence-console"


def test_frontier_route(monkeypatch):
    expected = {"frontier": {"payload": {"profile_id": "profile.high_assurance_enterprise_agent"}}, "provenance": None, "recent": []}
    monkeypatch.setattr(main.service, "get_frontier_view", lambda limit=20: expected)
    resp = client.get("/v1/console/frontier?limit=7")
    assert resp.status_code == 200
    assert resp.json() == expected


def test_model_route(monkeypatch):
    expected = {"model_release_id": "model.semantic-stack.2026-04-05", "dossier": None, "attribution": None, "recent": []}
    monkeypatch.setattr(main.service, "get_model_view", lambda model_release_id, limit=30: expected)
    resp = client.get("/v1/console/models/model.semantic-stack.2026-04-05?limit=9")
    assert resp.status_code == 200
    assert resp.json() == expected


def test_coverage_route(monkeypatch):
    expected = {"coverage": None, "radar": None, "recent": []}
    monkeypatch.setattr(main.service, "get_coverage_view", lambda limit=20: expected)
    resp = client.get("/v1/console/coverage?limit=11")
    assert resp.status_code == 200
    assert resp.json() == expected


def test_recent_events_route(monkeypatch):
    expected = {"services": ["eval-fabric-api", "lampstand"], "items": []}
    monkeypatch.setattr(main.service, "get_recent_events_view", lambda limit=25, per_service_limit=15: expected)
    resp = client.get("/v1/console/recent-events?limit=10&per_service_limit=3")
    assert resp.status_code == 200
    assert resp.json() == expected


def test_recent_telemetry_route(monkeypatch):
    expected = {"service": "telemetry-runtime", "items": [{"event_type": "reliability.conversation.stream.completed"}]}
    monkeypatch.setattr(main.service, "get_recent_telemetry_view", lambda service_name="telemetry-runtime", limit=25: expected)
    resp = client.get("/v1/console/telemetry?limit=10&service_name=telemetry-runtime")
    assert resp.status_code == 200
    assert resp.json() == expected


def test_console_ui_contains_fetch_targets():
    resp = client.get("/console/evidence")
    assert resp.status_code == 200
    body = resp.text
    assert "Evidence Console" in body
    assert "/v1/console/frontier" in body
    assert "/v1/console/models/model.semantic-stack.2026-04-05" in body
    assert "/v1/console/coverage" in body
    assert "/v1/console/recent-events" in body
    assert "/v1/console/telemetry" in body
