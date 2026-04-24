from __future__ import annotations

from dataclasses import dataclass

from app.models import LearningSearchRecord
from app.repositories import academy_repository


@dataclass
class PlatformSearchResult:
    result_id: str
    source: str
    entity_type: str
    title: str
    snippet: str
    path_or_uri: str
    final_score: float
    open_cloud: bool = True
    summarize: bool = True
    create_task: bool = True
    draft_reply: bool = False


def reset_academy_records() -> None:
    academy_repository.clear()


def ingest_academy_record(record: LearningSearchRecord) -> LearningSearchRecord:
    return academy_repository.ingest(record)


def query_academy_records(text: str, enabled: bool = True) -> list[PlatformSearchResult]:
    if not enabled or not text.strip():
        return []
    needle = text.lower()
    results: list[PlatformSearchResult] = []
    for record in academy_repository.list_records():
        haystack = " ".join([record.title, record.text, record.target_ref]).lower()
        if needle not in haystack:
            continue
        results.append(
            PlatformSearchResult(
                result_id=record.header.object_id,
                source=record.source,
                entity_type=record.entity_type,
                title=record.title,
                snippet=record.text,
                path_or_uri=f"alexandrian://learning-search/{record.header.object_id}",
                final_score=record.final_score,
            )
        )
    return results


def query_platform_workspace(text: str, enabled: bool = True) -> list[PlatformSearchResult]:
    if not enabled or not text.strip():
        return []
    return [
        PlatformSearchResult(
            result_id=f"platform-{text}",
            source="PLATFORM",
            entity_type="DOCUMENT",
            title=f"Workspace result placeholder for: {text}",
            snippet=f"Matched workspace content for query: {text}",
            path_or_uri=f"workspace://documents/{text}",
            final_score=1.0,
        )
    ]
