from fastapi import FastAPI

from app.backends import ingest_academy_record, query_academy_records, query_platform_workspace
from app.models import LearningSearchRecord, SearchRequest, SearchResult, SearchResultScore

app = FastAPI(title="search-orchestrator", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "search-orchestrator"}


@app.post("/v1/search/ingest/academy", response_model=LearningSearchRecord)
def ingest_academy(body: LearningSearchRecord) -> LearningSearchRecord:
    return ingest_academy_record(body)


@app.post("/v0/search/query")
def search_query(body: SearchRequest) -> dict[str, object]:
    results: list[dict[str, object]] = []
    scope = body.scope or None
    enabled = scope is not None and scope.cloud_workspace

    for item in query_platform_workspace(text=body.text, enabled=enabled):
        result = SearchResult(
            result_id=item.result_id,
            source=item.source,
            entity_type=item.entity_type,
            title=item.title,
            snippet=item.snippet,
            path_or_uri=item.path_or_uri,
            score=SearchResultScore(final=item.final_score),
        )
        results.append(result.model_dump())

    for item in query_academy_records(text=body.text, enabled=enabled):
        result = SearchResult(
            result_id=item.result_id,
            source=item.source,
            entity_type=item.entity_type,
            title=item.title,
            snippet=item.snippet,
            path_or_uri=item.path_or_uri,
            score=SearchResultScore(final=item.final_score),
        )
        results.append(result.model_dump())

    return {
        "query_id": body.query_id,
        "actor_id": body.actor_id,
        "mode": body.mode,
        "results": results[: body.limit],
    }
