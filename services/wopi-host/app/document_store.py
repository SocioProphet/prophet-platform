from __future__ import annotations

from pathlib import Path


class DocumentPayloadStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, document_id: str) -> Path:
        return self.root / f"{document_id}.bin"

    def get_bytes(self, document_id: str) -> bytes | None:
        path = self._path(document_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def put_bytes(self, document_id: str, payload: bytes) -> None:
        self._path(document_id).write_bytes(payload)
