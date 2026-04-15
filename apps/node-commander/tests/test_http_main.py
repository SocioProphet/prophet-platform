from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "node-commander"


def test_readyz() -> None:
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_status_route() -> None:
    resp = client.get("/v1/node-commander/status")
    assert resp.status_code == 200
    assert resp.json()["service"] == "node-commander"
    assert resp.json()["runtime"]["container_runtime"] == "podman"


def test_heartbeat_route() -> None:
    resp = client.get("/v1/node-commander/heartbeat")
    assert resp.status_code == 200
    assert resp.json()["heartbeat"] == "ok"
