from fastapi import FastAPI

app = FastAPI(title="wopi-host", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "wopi-host"}


@app.get("/v0/wopi/check-file-info/{document_id}")
def check_file_info(document_id: str) -> dict[str, object]:
    return {
        "document_id": document_id,
        "base_file_name": f"{document_id}.odt",
        "supports_locks": True,
        "supports_update": True,
        "user_can_write": True,
    }


@app.post("/v0/wopi/lock/{document_id}")
def acquire_lock(document_id: str) -> dict[str, object]:
    return {
        "document_id": document_id,
        "session_id": f"session-{document_id}",
        "lock_token": f"lock-{document_id}",
        "status": "LOCKED",
    }


@app.post("/v0/wopi/writeback/{document_id}")
def writeback(document_id: str) -> dict[str, object]:
    return {
        "document_id": document_id,
        "session_id": f"session-{document_id}",
        "version_id": f"version-{document_id}-001",
        "status": "WRITTEN",
    }
