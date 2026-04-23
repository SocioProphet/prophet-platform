from fastapi import FastAPI, Response
from pydantic import BaseModel

from services.wopi_host.app.document_store import DocumentPayloadStore
from services.wopi_host.app.file_store import FileBackedWOPIStore
from services.wopi_host.app.store import store

app = FastAPI(title="wopi-host", version="0.1.0")
file_store = FileBackedWOPIStore("/tmp/sourceos-wopi-store")
document_store = DocumentPayloadStore("/tmp/sourceos-wopi-docs")


class PutFileRequest(BaseModel):
    payload: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "wopi-host"}


@app.get("/v0/wopi/check-file-info/{document_id}")
def check_file_info(document_id: str) -> dict[str, object]:
    state = store.get(document_id)
    payload = document_store.get_bytes(document_id)
    return {
        "document_id": document_id,
        "base_file_name": f"{document_id}.odt",
        "supports_locks": True,
        "supports_update": True,
        "user_can_write": True,
        "version_counter": 0 if state is None else state.version_counter,
        "has_payload": payload is not None,
    }


@app.post("/v0/wopi/lock/{document_id}")
def acquire_lock(document_id: str) -> dict[str, object]:
    state = store.acquire_lock(document_id)
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "lock_token": state.lock_token,
        "status": "LOCKED",
        "updated_at": state.updated_at,
    }


@app.post("/v0/wopi/writeback/{document_id}")
def writeback(document_id: str) -> dict[str, object]:
    state = store.writeback(document_id)
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "version_id": f"version-{state.document_id}-{state.version_counter:03d}",
        "status": "WRITTEN",
        "updated_at": state.updated_at,
    }


@app.post("/v0/wopi/file-writeback/{document_id}")
def file_writeback(document_id: str) -> dict[str, object]:
    state = file_store.writeback(document_id)
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "version_id": f"version-{state.document_id}-{state.version_counter:03d}",
        "status": "WRITTEN",
        "updated_at": state.updated_at,
        "store": "file",
    }


@app.get("/v0/wopi/get-file/{document_id}")
def get_file(document_id: str):
    payload = document_store.get_bytes(document_id)
    if payload is None:
        return Response(status_code=404)
    return Response(content=payload, media_type="application/octet-stream")


@app.post("/v0/wopi/put-file/{document_id}")
def put_file(document_id: str, body: PutFileRequest) -> dict[str, object]:
    document_store.put_bytes(document_id, body.payload.encode("utf-8"))
    state = store.writeback(document_id)
    return {
        "document_id": state.document_id,
        "version_id": f"version-{state.document_id}-{state.version_counter:03d}",
        "status": "WRITTEN",
        "store": "payload",
    }
