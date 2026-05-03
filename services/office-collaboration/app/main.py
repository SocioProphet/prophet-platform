from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="office-collaboration", version="0.1.0")
THREADS: dict[str, dict[str, object]] = {}
THREAD_MESSAGES: dict[str, list[dict[str, object]]] = {}
THREAD_EVENTS: dict[str, list[dict[str, object]]] = {}
SUGGESTIONS: dict[str, dict[str, object]] = {}
SUGGESTION_EVENTS: dict[str, list[dict[str, object]]] = {}


class ThreadIn(BaseModel):
    thread_id: str
    document_id: str
    thread_type: str
    semantic_unit_ref: str | None = None


class ThreadMessageIn(BaseModel):
    message_id: str
    actor_ref: str
    body: str


class ThreadStatusIn(BaseModel):
    status: str
    version_id: str | None = None
    receipt_ref: str | None = None


class SuggestionIn(BaseModel):
    suggestion_id: str
    document_id: str
    semantic_unit_ref: str | None = None
    before_ref: str | None = None
    after_ref: str | None = None


class SuggestionStatusIn(BaseModel):
    status: str
    version_id: str | None = None
    receipt_ref: str | None = None


@app.get('/healthz')
def healthz() -> dict[str, str]:
    return {'status': 'ok', 'service': 'office-collaboration'}


@app.post('/v0/office-collaboration/threads')
def create_thread(body: ThreadIn) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'thread_id': body.thread_id,
        'document_id': body.document_id,
        'thread_type': body.thread_type,
        'semantic_unit_ref': body.semantic_unit_ref,
        'status': 'OPEN',
        'version_id': None,
        'receipt_ref': None,
        'created_at': now,
        'updated_at': now,
    }
    THREADS[body.thread_id] = record
    THREAD_MESSAGES[body.thread_id] = []
    THREAD_EVENTS[body.thread_id] = [{'event_type': 'THREAD_CREATED', 'thread_id': body.thread_id, 'created_at': now}]
    return record


@app.get('/v0/office-collaboration/threads/{thread_id}')
def get_thread(thread_id: str) -> dict[str, object]:
    record = THREADS.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail='thread not found')
    return record


@app.get('/v0/office-collaboration/documents/{document_id}/threads')
def list_document_threads(document_id: str) -> dict[str, object]:
    return {'document_id': document_id, 'threads': [item for item in THREADS.values() if item['document_id'] == document_id]}


@app.post('/v0/office-collaboration/threads/{thread_id}/messages')
def add_thread_message(thread_id: str, body: ThreadMessageIn) -> dict[str, object]:
    thread = THREADS.get(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail='thread not found')
    now = datetime.now(timezone.utc).isoformat()
    message = {'message_id': body.message_id, 'thread_id': thread_id, 'actor_ref': body.actor_ref, 'body': body.body, 'created_at': now}
    THREAD_MESSAGES.setdefault(thread_id, []).append(message)
    THREAD_EVENTS.setdefault(thread_id, []).append({'event_type': 'MESSAGE_ADDED', 'thread_id': thread_id, 'message_id': body.message_id, 'actor_ref': body.actor_ref, 'created_at': now})
    thread['updated_at'] = now
    return message


@app.get('/v0/office-collaboration/threads/{thread_id}/messages')
def list_thread_messages(thread_id: str) -> dict[str, object]:
    if thread_id not in THREADS:
        raise HTTPException(status_code=404, detail='thread not found')
    return {'thread_id': thread_id, 'messages': THREAD_MESSAGES.get(thread_id, [])}


@app.get('/v0/office-collaboration/threads/{thread_id}/events')
def list_thread_events(thread_id: str) -> dict[str, object]:
    if thread_id not in THREADS:
        raise HTTPException(status_code=404, detail='thread not found')
    return {'thread_id': thread_id, 'events': THREAD_EVENTS.get(thread_id, [])}


@app.post('/v0/office-collaboration/threads/{thread_id}/status')
def update_thread_status(thread_id: str, body: ThreadStatusIn) -> dict[str, object]:
    record = THREADS.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail='thread not found')
    now = datetime.now(timezone.utc).isoformat()
    record['status'] = body.status
    record['version_id'] = body.version_id
    record['receipt_ref'] = body.receipt_ref
    record['updated_at'] = now
    THREAD_EVENTS.setdefault(thread_id, []).append({'event_type': 'THREAD_STATUS_UPDATED', 'thread_id': thread_id, 'status': body.status, 'version_id': body.version_id, 'receipt_ref': body.receipt_ref, 'created_at': now})
    return record


@app.post('/v0/office-collaboration/suggestions')
def create_suggestion(body: SuggestionIn) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'suggestion_id': body.suggestion_id,
        'document_id': body.document_id,
        'semantic_unit_ref': body.semantic_unit_ref,
        'before_ref': body.before_ref,
        'after_ref': body.after_ref,
        'status': 'PROPOSED',
        'version_id': None,
        'receipt_ref': None,
        'created_at': now,
        'updated_at': now,
    }
    SUGGESTIONS[body.suggestion_id] = record
    SUGGESTION_EVENTS[body.suggestion_id] = [{'event_type': 'SUGGESTION_CREATED', 'suggestion_id': body.suggestion_id, 'created_at': now}]
    return record


@app.get('/v0/office-collaboration/suggestions/{suggestion_id}')
def get_suggestion(suggestion_id: str) -> dict[str, object]:
    record = SUGGESTIONS.get(suggestion_id)
    if record is None:
        raise HTTPException(status_code=404, detail='suggestion not found')
    return record


@app.get('/v0/office-collaboration/suggestions/{suggestion_id}/events')
def list_suggestion_events(suggestion_id: str) -> dict[str, object]:
    if suggestion_id not in SUGGESTIONS:
        raise HTTPException(status_code=404, detail='suggestion not found')
    return {'suggestion_id': suggestion_id, 'events': SUGGESTION_EVENTS.get(suggestion_id, [])}


@app.get('/v0/office-collaboration/documents/{document_id}/suggestions')
def list_document_suggestions(document_id: str) -> dict[str, object]:
    return {'document_id': document_id, 'suggestions': [item for item in SUGGESTIONS.values() if item['document_id'] == document_id]}


@app.post('/v0/office-collaboration/suggestions/{suggestion_id}/status')
def update_suggestion_status(suggestion_id: str, body: SuggestionStatusIn) -> dict[str, object]:
    record = SUGGESTIONS.get(suggestion_id)
    if record is None:
        raise HTTPException(status_code=404, detail='suggestion not found')
    now = datetime.now(timezone.utc).isoformat()
    record['status'] = body.status
    record['version_id'] = body.version_id
    record['receipt_ref'] = body.receipt_ref
    record['updated_at'] = now
    SUGGESTION_EVENTS.setdefault(suggestion_id, []).append({'event_type': 'SUGGESTION_STATUS_UPDATED', 'suggestion_id': suggestion_id, 'status': body.status, 'version_id': body.version_id, 'receipt_ref': body.receipt_ref, 'created_at': now})
    return record
