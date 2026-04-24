from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlatformSearchResult:
    result_id: str
    source: str
    entity_type: str
    title: str
    final_score: float


def query_platform_workspace(text: str, enabled: bool = True) -> list[PlatformSearchResult]:
    if not enabled or not text.strip():
        return []
    return [
        PlatformSearchResult(
            result_id=f"platform-{text}",
            source="PLATFORM",
            entity_type="DOCUMENT",
            title=f"Workspace result placeholder for: {text}",
            final_score=1.0,
        )
    ]
