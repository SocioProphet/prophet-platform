from fastapi import FastAPI

from services.search_orchestrator.app.models import SearchRequest, SearchResult, SearchResultScore

app = FastAPI(title="search-orchestrator", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "search-orchestrator"}


@app.post("/v0/search/query")
def search_query(body: SearchRequest) -> dict[str, object]:
    results: list[dict[str, object]] = []
    scope = body.scope or None

    if scope is not None and scope.cloud_workspace and body.text.strip():
        result = SearchResult(
            result_id=f"platform-{body.query_id}",
            source="PLATFORM",
            entity_type="DOCUMENT",
            title=f"Workspace result placeholder for: {body.text}",
            score=SearchResultScore(final=1.0),
        )
        results.append(result.model_dump())

    return {
        "query_id": body.query_id,
        "actor_id": body.actor_id,
        "mode": body.mode,
        "results": results,
    }
