from __future__ import annotations

import json
import os
from pathlib import Path

from app.models import LearningSearchRecord


class AcademySearchRepository:
    def ingest(self, record: LearningSearchRecord) -> LearningSearchRecord:
        raise NotImplementedError

    def list_records(self) -> list[LearningSearchRecord]:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class InMemoryAcademySearchRepository(AcademySearchRepository):
    def __init__(self) -> None:
        self._records: dict[str, LearningSearchRecord] = {}

    def ingest(self, record: LearningSearchRecord) -> LearningSearchRecord:
        self._records[record.header.object_id] = record
        return record

    def list_records(self) -> list[LearningSearchRecord]:
        return list(self._records.values())

    def clear(self) -> None:
        self._records.clear()


class JsonFileAcademySearchRepository(AcademySearchRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]\n", encoding="utf-8")

    def _load(self) -> list[LearningSearchRecord]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [LearningSearchRecord.model_validate(item) for item in raw]

    def _save(self, records: list[LearningSearchRecord]) -> None:
        payload = [record.model_dump(mode="json") for record in records]
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    def ingest(self, record: LearningSearchRecord) -> LearningSearchRecord:
        records = {item.header.object_id: item for item in self._load()}
        records[record.header.object_id] = record
        self._save(list(records.values()))
        return record

    def list_records(self) -> list[LearningSearchRecord]:
        return self._load()

    def clear(self) -> None:
        self._save([])


def build_academy_repository() -> AcademySearchRepository:
    path = os.environ.get("SEARCH_ORCHESTRATOR_ACADEMY_STORE")
    if path:
        return JsonFileAcademySearchRepository(Path(path))
    return InMemoryAcademySearchRepository()


academy_repository: AcademySearchRepository = build_academy_repository()
