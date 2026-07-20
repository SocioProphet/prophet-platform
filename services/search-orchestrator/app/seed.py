"""Boot-seed the academy repository with a bundled corpus on startup.

Opt-in: seeding only runs when SEARCH_ORCHESTRATOR_ACADEMY_SEED points at a JSONL file
(one LearningSearchRecord per line). Deploy sets it to the bundled 8.01 corpus; tests
leave it unset so the repository starts empty. Idempotent (skips when records already
exist, keyed by object_id) and best-effort (a bad line or read error never blocks boot).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.backends import ingest_academy_record
from app.models import LearningSearchRecord
from app.repositories import academy_repository


def seed_academy_if_empty() -> int:
    seed_env = os.environ.get("SEARCH_ORCHESTRATOR_ACADEMY_SEED")
    if not seed_env:
        return 0
    try:
        if academy_repository.list_records():
            return 0
        seed_path = Path(seed_env)
        if not seed_path.exists():
            return 0
        seeded = 0
        for line in seed_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ingest_academy_record(LearningSearchRecord.model_validate(json.loads(line)))
                seeded += 1
            except Exception:
                continue
        return seeded
    except Exception:
        return 0
