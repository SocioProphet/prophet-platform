from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="search-orchestrator", version="0.1.0")


class SearchRequest(BaseModel):
    query_id: str
    actor_id: str
    text: str
    mode: str
    limit: int


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "search-orchestrator"}


@app.post("/v0/search/query")
def search_query(body: SearchRequest) -> dict[str, object]:
    return {
        "query_id": body.query_id,
        "actor_id": body.actor_id,
        "mode": body.mode,
        "results": [],
    }
