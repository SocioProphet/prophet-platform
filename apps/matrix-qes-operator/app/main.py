from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .commands import parse_command
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
