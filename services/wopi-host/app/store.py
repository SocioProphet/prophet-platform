from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SessionState:
    document_id: str
    session_id: str
    lock_token: str
    version_counter: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InMemoryWOPIStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def acquire_lock(self, document_id: str) -> SessionState:
        state = SessionState(
            document_id=document_id,
            session_id=f"session-{document_id}",
            lock_token=f"lock-{document_id}",
        )
        self._sessions[document_id] = state
        return state

    def refresh_lock(self, document_id: str) -> SessionState | None:
        state = self._sessions.get(document_id)
        if state is None:
            return None
        state.updated_at = datetime.now(timezone.utc).isoformat()
        return state

    def release_lock(self, document_id: str) -> SessionState | None:
        return self._sessions.pop(document_id, None)

    def writeback(self, document_id: str) -> SessionState:
        state = self._sessions.get(document_id)
        if state is None:
            state = self.acquire_lock(document_id)
        state.version_counter += 1
        state.updated_at = datetime.now(timezone.utc).isoformat()
        return state

    def get(self, document_id: str) -> SessionState | None:
        return self._sessions.get(document_id)


store = InMemoryWOPIStore()
