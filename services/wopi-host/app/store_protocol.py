from __future__ import annotations

from typing import Protocol

from services.wopi_host.app.store import SessionState


class WOPIStore(Protocol):
    def acquire_lock(self, document_id: str) -> SessionState: ...

    def writeback(self, document_id: str) -> SessionState: ...

    def get(self, document_id: str) -> SessionState | None: ...
