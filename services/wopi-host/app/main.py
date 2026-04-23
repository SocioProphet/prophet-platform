from fastapi import FastAPI

from services.wopi_host.app.file_store import FileBackedWOPIStore
from services.wopi_host.app.store import store

app = FastAPI(title="wopi-host", version="0.1.0")
file_store = FileBackedWOPIStore("/tmp/sourceos-wopi-store")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "wopi-host"}


@app.get("/v0/wopi/check-file-info/{document_id}")
def check_file_info(document_id: str) -> dict[str, object]:
    state = store.get(document_id)
    return {
        "document_id": document_id,
        "base_file_name": f"{document_id}.odt",
        "supports_locks": True,
        "supports_update": True,
        "user_can_write": True,
        "version_counter": 0 if state is None else state.version_counter,
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
