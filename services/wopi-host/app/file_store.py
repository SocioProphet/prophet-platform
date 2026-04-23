from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from services.wopi_host.app.store import SessionState


class FileBackedWOPIStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, document_id: str) -> Path:
        return self.root / f"{document_id}.json"

    def acquire_lock(self, document_id: str) -> SessionState:
        state = SessionState(
            document_id=document_id,
            session_id=f"session-{document_id}",
            lock_token=f"lock-{document_id}",
        )
        self._path(document_id).write_text(json.dumps(asdict(state)), encoding="utf-8")
        return state

    def writeback(self, document_id: str) -> SessionState:
        state = self.get(document_id)
        if state is None:
            state = self.acquire_lock(document_id)
        state.version_counter += 1
        self._path(document_id).write_text(json.dumps(asdict(state)), encoding="utf-8")
        return state

    def get(self, document_id: str) -> SessionState | None:
        path = self._path(document_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SessionState(**payload)
