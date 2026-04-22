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
