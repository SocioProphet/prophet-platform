from fastapi import FastAPI

from app.backends import ingest_academy_record, query_academy_records, query_platform_workspace
from app.metrics import increment, snapshot
from app.models import LearningSearchRecord, SearchRequest, SearchResult, SearchResultActions, SearchResultScore
from app.policy import describe_academy_policy_evaluator
from app.repositories import describe_academy_repository

app = FastAPI(title="search-orchestrator", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "search-orchestrator"}


@app.get("/v1/search/debug/config")
def debug_config() -> dict[str, object]:
    return {
        "service": "search-orchestrator",
        "academy_repository": describe_academy_repository(),
        "academy_policy": describe_academy_policy_evaluator(),
        "redaction": "paths, URLs, and secrets are not returned",
    }


@app.get("/v1/search/debug/metrics")
def debug_metrics() -> dict[str, object]:
    return {
        "service": "search-orchestrator",
        "metrics": snapshot(),
        "redaction": "metrics contain counters only; paths, URLs, actor ids, queries, and secrets are not returned",
    }


@app.post("/v1/search/ingest/academy", response_model=LearningSearchRecord)
def ingest_academy(body: LearningSearchRecord) -> LearningSearchRecord:
    increment("academy_ingest_total")
    return ingest_academy_record(body)


def _actions_for(item) -> SearchResultActions:
    return SearchResultActions(
        open_cloud=item.open_cloud,
        summarize=item.summarize,
        create_task=item.create_task,
        draft_reply=item.draft_reply,
    )


@app.post("/v0/search/query")
def search_query(body: SearchRequest) -> dict[str, object]:
    increment("search_query_total")
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
            actions=_actions_for(item),
        )
        results.append(result.model_dump())

    academy_items = query_academy_records(body.text, enabled, body.actor_id, body.workspace_id, body.jurisdiction_id)
    increment("academy_result_total", len(academy_items))
    for item in academy_items:
        result = SearchResult(
            result_id=item.result_id,
            source=item.source,
            entity_type=item.entity_type,
            title=item.title,
            snippet=item.snippet,
            path_or_uri=item.path_or_uri,
            score=SearchResultScore(final=item.final_score),
            actions=_actions_for(item),
        )
        results.append(result.model_dump())

    return {
        "query_id": body.query_id,
        "actor_id": body.actor_id,
        "mode": body.mode,
        "results": results[: body.limit],
    }
