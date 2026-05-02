from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="office-collaboration", version="0.1.0")
THREADS: dict[str, dict[str, object]] = {}
SUGGESTIONS: dict[str, dict[str, object]] = {}


class ThreadIn(BaseModel):
    thread_id: str
    document_id: str
    thread_type: str
    semantic_unit_ref: str | None = None


class SuggestionIn(BaseModel):
    suggestion_id: str
    document_id: str
    semantic_unit_ref: str | None = None
    before_ref: str | None = None
    after_ref: str | None = None


class SuggestionStatusIn(BaseModel):
    status: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "office-collaboration"}


@app.post("/v0/office-collaboration/threads")
def create_thread(body: ThreadIn) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "thread_id": body.thread_id,
        "document_id": body.document_id,
        "thread_type": body.thread_type,
        "semantic_unit_ref": body.semantic_unit_ref,
        "status": "OPEN",
        "created_at": now,
        "updated_at": now,
    }
    THREADS[body.thread_id] = record
    return record


@app.get("/v0/office-collaboration/threads/{thread_id}")
def get_thread(thread_id: str) -> dict[str, object]:
    record = THREADS.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return record


@app.post("/v0/office-collaboration/suggestions")
def create_suggestion(body: SuggestionIn) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "suggestion_id": body.suggestion_id,
        "document_id": body.document_id,
        "semantic_unit_ref": body.semantic_unit_ref,
        "before_ref": body.before_ref,
        "after_ref": body.after_ref,
        "status": "PROPOSED",
        "created_at": now,
        "updated_at": now,
    }
    SUGGESTIONS[body.suggestion_id] = record
    return record


@app.post("/v0/office-collaboration/suggestions/{suggestion_id}/status")
def update_suggestion_status(suggestion_id: str, body: SuggestionStatusIn) -> dict[str, object]:
    record = SUGGESTIONS.get(suggestion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="suggestion not found")
    record["status"] = body.status
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    return record
