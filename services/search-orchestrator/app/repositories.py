from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

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


class LampstandJsonlAcademySearchRepository(AcademySearchRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def ingest(self, record: LearningSearchRecord) -> LearningSearchRecord:
        records = {item.header.object_id: item for item in self.list_records()}
        records[record.header.object_id] = record
        with self.path.open("w", encoding="utf-8") as handle:
            for item in records.values():
                handle.write(json.dumps(item.model_dump(mode="json"), sort_keys=False) + "\n")
        return record

    def list_records(self) -> list[LearningSearchRecord]:
        records: list[LearningSearchRecord] = []
        if not self.path.exists():
            return records
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(LearningSearchRecord.model_validate(json.loads(line)))
        return records

    def clear(self) -> None:
        self.path.write_text("", encoding="utf-8")


class LampstandCarrierAcademySearchRepository(AcademySearchRepository):
    def __init__(
        self,
        payload_dir: Path,
        *,
        scope_ref: str = "scope://academy/search",
        zone_ref: str = "zone://edge",
        topic_ref: str = "topic://academy/search",
    ) -> None:
        self.payload_dir = payload_dir
        self.scope_ref = scope_ref
        self.zone_ref = zone_ref
        self.topic_ref = topic_ref
        self.payload_dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, record: LearningSearchRecord) -> Path:
        safe_id = record.header.object_id.replace("/", "_").replace(":", "_")
        return self.payload_dir / f"{safe_id}.LearningSearchRecord.json"

    def _ingest_path(self, path: Path) -> dict[str, Any]:
        try:
            from prophet_platform_lampstand.ingest import ingest_path
        except ModuleNotFoundError:
            repo_root = Path(__file__).resolve().parents[3]
            lampstand_src = repo_root / "apps" / "lampstand" / "src"
            sys.path.insert(0, str(lampstand_src))
            from prophet_platform_lampstand.ingest import ingest_path
        return ingest_path(
            file_path=str(path),
            scope_ref=self.scope_ref,
            service_ref="services/search-orchestrator",
            classifiers=[
                "source:alexandrian-academy",
                "entity:learning-search-record",
                "service:search-orchestrator",
            ],
            zone_ref=self.zone_ref,
            topic_ref=self.topic_ref,
        )

    def ingest(self, record: LearningSearchRecord) -> LearningSearchRecord:
        path = self._record_path(record)
        path.write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=False) + "\n", encoding="utf-8")
        result = self._ingest_path(path)
        path.with_suffix(".lampstand-ingest-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record

    def list_records(self) -> list[LearningSearchRecord]:
        records: list[LearningSearchRecord] = []
        for path in sorted(self.payload_dir.glob("*.LearningSearchRecord.json")):
            records.append(LearningSearchRecord.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return records

    def clear(self) -> None:
        for path in self.payload_dir.glob("*.LearningSearchRecord.json"):
            path.unlink()
        for path in self.payload_dir.glob("*.lampstand-ingest-result.json"):
            path.unlink()


def build_academy_repository() -> AcademySearchRepository:
    carrier_dir = os.environ.get("SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR")
    if carrier_dir:
        return LampstandCarrierAcademySearchRepository(Path(carrier_dir))
    lampstand_path = os.environ.get("SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_JSONL")
    if lampstand_path:
        return LampstandJsonlAcademySearchRepository(Path(lampstand_path))
    path = os.environ.get("SEARCH_ORCHESTRATOR_ACADEMY_STORE")
    if path:
        return JsonFileAcademySearchRepository(Path(path))
    return InMemoryAcademySearchRepository()


academy_repository: AcademySearchRepository = build_academy_repository()
