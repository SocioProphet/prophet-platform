from __future__ import annotations

import sys
from pathlib import Path

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
# /execute endpoint — dispatch verbs
# ---------------------------------------------------------------------------


def test_execute_runbook_verb(monkeypatch) -> None:
    """POST /execute with a dispatch verb (runbook) calls the shell handler."""
    import subprocess

    monkeypatch.setattr(
        "app.dispatch.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="runbook-alpha\nrunbook-beta", stderr=""
        ),
    )

    resp = client.post(
        "/v1/matrix-qes/commands/execute",
        json={
            "actor": "@ops:example.org",
            "room_id": "!incident:example.org",
            "thread_id": "$thread3",
            "body": "!qes runbook list",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["verb"] == "runbook"
    assert "runbook-alpha" in body["reply"]
    # Dispatch replies must not have state-machine fields.
    assert "current_state" not in body


def test_execute_incident_verb_ack(monkeypatch, tmp_path: Path) -> None:
    """POST /execute with an incident verb (ack) falls through to the state machine."""
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    main.store = main.SQLiteThreadStateStore()

    resp = client.post(
        "/v1/matrix-qes/commands/execute",
        json={
            "actor": "@ops:example.org",
            "room_id": "!incident:example.org",
            "thread_id": "$thread4",
            "body": "!qes ack",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["previous_state"] == "triage"
    assert body["current_state"] == "acknowledged"
    # State-machine response must not have dispatch-only fields.
    assert "reply" not in body
