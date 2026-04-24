from __future__ import annotations

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


academy_repository: AcademySearchRepository = InMemoryAcademySearchRepository()
