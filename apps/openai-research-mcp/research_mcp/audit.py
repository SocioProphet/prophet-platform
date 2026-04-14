from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class JsonlAuditSink:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, payload: dict):
        row = dict(payload)
        row.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
