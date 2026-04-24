from __future__ import annotations

import json
from pathlib import Path


class DocumentVersionStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, document_id: str) -> Path:
        return self.root / f"{document_id}.versions.json"

    def append(self, document_id: str, version_id: str) -> None:
        path = self._path(document_id)
        versions = self.list_versions(document_id)
        versions.append(version_id)
        path.write_text(json.dumps(versions), encoding="utf-8")

    def list_versions(self, document_id: str) -> list[str]:
        path = self._path(document_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))
