from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main  # type: ignore

client = TestClient(main.app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "matrix-qes-operator"


def test_parse_command() -> None:
    resp = client.post(
        "/v1/matrix-qes/commands/parse",
        json={
            "actor": "@ops:example.org",
            "room_id": "!incident:example.org",
            "thread_id": "$thread1",
            "body": "!qes ack",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["command"]["verb"] == "ack"
    assert body["command"]["args"] == []


def test_apply_transition_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    main.store = main.SQLiteThreadStateStore()

    resp = client.post(
        "/v1/matrix-qes/commands/apply",
        json={
            "actor": "@ops:example.org",
            "room_id": "!incident:example.org",
            "thread_id": "$thread1",
            "body": "!qes ack",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["previous_state"] == "triage"
    assert body["current_state"] == "acknowledged"

    resp2 = client.post(
        "/v1/matrix-qes/commands/apply",
        json={
            "actor": "@ops:example.org",
            "room_id": "!incident:example.org",
            "thread_id": "$thread1",
            "body": "!qes investigate",
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["previous_state"] == "acknowledged"
    assert body2["current_state"] == "investigating"


def test_invalid_transition(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    main.store = main.SQLiteThreadStateStore()

    resp = client.post(
        "/v1/matrix-qes/commands/apply",
        json={
            "actor": "@ops:example.org",
            "room_id": "!incident:example.org",
            "thread_id": "$thread2",
            "body": "!qes close",
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /v1/matrix-qes/rooms
# ---------------------------------------------------------------------------


def test_rooms_with_token_returns_room_list(monkeypatch) -> None:
    monkeypatch.setenv("MATRIX_HOMESERVER_URL", "https://matrix.example.org")
    monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")

    fake_payload = json.dumps(
        {"joined_rooms": ["!roomA:example.org", "!roomB:example.org"]}
    ).encode()

    mock_response = MagicMock()
    mock_response.read.return_value = fake_payload
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("app.main.urllib.request.urlopen", return_value=mock_response):
        resp = client.get("/v1/matrix-qes/rooms")

    assert resp.status_code == 200
    body = resp.json()
    assert "!roomA:example.org" in body["rooms"]
    assert "!roomB:example.org" in body["rooms"]
    assert "warning" not in body


def test_rooms_without_token_returns_empty_with_warning(monkeypatch) -> None:
    monkeypatch.delenv("MATRIX_HOMESERVER_URL", raising=False)
    monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)

    resp = client.get("/v1/matrix-qes/rooms")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rooms"] == []
    assert "warning" in body
    assert "MATRIX_ACCESS_TOKEN" in body["warning"]
