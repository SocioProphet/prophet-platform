from __future__ import annotations

import os
import urllib.request
import urllib.error
import json
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import dispatch
from .commands import is_dispatch_verb, parse_command
from .state_machine import IncidentThreadState, apply_transition, transition_map
from .store import SQLiteThreadStateStore

app = FastAPI(title="Prophet Platform Matrix QES Operator", version="0.1.0")
store = SQLiteThreadStateStore()


class ParseCommandRequest(BaseModel):
    actor: str
    room_id: str
    thread_id: str | None = None
    body: str


class ApplyCommandRequest(BaseModel):
    actor: str
    room_id: str
    thread_id: str | None = None
    body: str


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "service": "matrix-qes-operator"}


@app.get("/v1/matrix-qes/transitions")
def transitions() -> dict[str, Any]:
    return {"service": "matrix-qes-operator", "transitions": transition_map()}


@app.get("/v1/matrix-qes/rooms")
def list_rooms() -> dict[str, Any]:
    """Return the list of joined Matrix rooms for the configured homeserver."""
    homeserver = os.environ.get("MATRIX_HOMESERVER_URL", "").rstrip("/")
    token = os.environ.get("MATRIX_ACCESS_TOKEN", "")

    if not homeserver or not token:
        return {"rooms": [], "warning": "MATRIX_ACCESS_TOKEN not configured"}

    url = f"{homeserver}/_matrix/client/v3/joined_rooms"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return {"rooms": data.get("joined_rooms", [])}
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail=f"Matrix API error: {exc.reason}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to reach Matrix homeserver: {exc}") from exc


@app.post("/v1/matrix-qes/commands/parse")
def parse(req: ParseCommandRequest) -> dict[str, Any]:
    try:
        command = parse_command(
            actor=req.actor,
            room_id=req.room_id,
            thread_id=req.thread_id,
            body=req.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "service": "matrix-qes-operator",
        "command": {
            "verb": command.verb,
            "args": command.args,
            "actor": command.actor,
            "room_id": command.room_id,
            "thread_id": command.thread_id,
        },
    }


@app.post("/v1/matrix-qes/commands/execute")
def execute(req: ApplyCommandRequest) -> dict[str, Any]:
    try:
        command = parse_command(
            actor=req.actor,
            room_id=req.room_id,
            thread_id=req.thread_id,
            body=req.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if is_dispatch_verb(command.verb):
        result = dispatch.execute(command)
        return {
            "service": "matrix-qes-operator",
            "reply": result.body,
            "ok": result.ok,
            "verb": command.verb,
            "actor": command.actor,
            "room_id": command.room_id,
            "thread_id": command.thread_id,
        }

    # Fall through to incident state-machine logic.
    current_record = store.get(room_id=req.room_id, thread_id=req.thread_id)
    current_state = current_record.state if current_record is not None else IncidentThreadState.TRIAGE
    try:
        new_state = apply_transition(current_state, command.verb)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    persisted = store.upsert(
        room_id=req.room_id,
        thread_id=req.thread_id,
        state=new_state,
        last_action=command.verb,
    )
    return {
        "service": "matrix-qes-operator",
        "action_id": str(uuid4()),
        "previous_state": current_state.value,
        "current_state": new_state.value,
        "room_id": persisted.room_id,
        "thread_id": persisted.thread_id,
        "incident_key": persisted.incident_key,
        "last_action": persisted.last_action,
        "updated_at": persisted.updated_at,
        "command": {
            "verb": command.verb,
            "args": command.args,
            "actor": command.actor,
        },
    }


@app.post("/v1/matrix-qes/commands/apply")
def apply(req: ApplyCommandRequest) -> dict[str, Any]:
    try:
        command = parse_command(
            actor=req.actor,
            room_id=req.room_id,
            thread_id=req.thread_id,
            body=req.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_record = store.get(room_id=req.room_id, thread_id=req.thread_id)
    current_state = current_record.state if current_record is not None else IncidentThreadState.TRIAGE
    try:
        new_state = apply_transition(current_state, command.verb)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    persisted = store.upsert(
        room_id=req.room_id,
        thread_id=req.thread_id,
        state=new_state,
        last_action=command.verb,
    )
    return {
        "service": "matrix-qes-operator",
        "action_id": str(uuid4()),
        "previous_state": current_state.value,
        "current_state": new_state.value,
        "room_id": persisted.room_id,
        "thread_id": persisted.thread_id,
        "incident_key": persisted.incident_key,
        "last_action": persisted.last_action,
        "updated_at": persisted.updated_at,
        "command": {
            "verb": command.verb,
            "args": command.args,
            "actor": command.actor,
        },
    }
