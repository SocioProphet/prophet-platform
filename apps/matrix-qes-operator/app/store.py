from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .state_machine import IncidentThreadState


@dataclass(slots=True)
class ThreadStateRecord:
    room_id: str
    thread_id: str | None
    incident_key: str
    state: IncidentThreadState
    last_action: str | None
    updated_at: str


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def default_db_path() -> Path:
    return state_home() / "prophet-platform" / "matrix-qes-operator" / "thread_state.sqlite3"


class SQLiteThreadStateStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS thread_state (
                    incident_key TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    thread_id TEXT,
                    state TEXT NOT NULL,
                    last_action TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def incident_key(room_id: str, thread_id: str | None) -> str:
        return f"{room_id}::{thread_id or 'main'}"

    def get(self, *, room_id: str, thread_id: str | None) -> ThreadStateRecord | None:
        incident_key = self.incident_key(room_id, thread_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT room_id, thread_id, incident_key, state, last_action, updated_at FROM thread_state WHERE incident_key = ?",
                (incident_key,),
            ).fetchone()
        if row is None:
            return None
        return ThreadStateRecord(
            room_id=row["room_id"],
            thread_id=row["thread_id"],
            incident_key=row["incident_key"],
            state=IncidentThreadState(row["state"]),
            last_action=row["last_action"],
            updated_at=row["updated_at"],
        )

    def upsert(self, *, room_id: str, thread_id: str | None, state: IncidentThreadState, last_action: str | None) -> ThreadStateRecord:
        incident_key = self.incident_key(room_id, thread_id)
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO thread_state(incident_key, room_id, thread_id, state, last_action, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_key) DO UPDATE SET
                    state = excluded.state,
                    last_action = excluded.last_action,
                    updated_at = excluded.updated_at
                """,
                (incident_key, room_id, thread_id, state.value, last_action, updated_at),
            )
        return ThreadStateRecord(
            room_id=room_id,
            thread_id=thread_id,
            incident_key=incident_key,
            state=state,
            last_action=last_action,
            updated_at=updated_at,
        )
