from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from fastapi import FastAPI, Response
from pydantic import BaseModel

from services.wopi_host.app.document_store import DocumentPayloadStore
from services.wopi_host.app.file_store import FileBackedWOPIStore
from services.wopi_host.app.store import SessionState, store
from services.wopi_host.app.version_store import DocumentVersionStore

app = FastAPI(title="wopi-host", version="0.1.0")
file_store = FileBackedWOPIStore("/tmp/sourceos-wopi-store")
document_store = DocumentPayloadStore("/tmp/sourceos-wopi-docs")
version_store = DocumentVersionStore("/tmp/sourceos-wopi-versions")

VERSION_RECORDS: dict[str, dict[str, object]] = {}
WRITEBACK_RECORDS: dict[str, dict[str, object]] = {}


class PutFileRequest(BaseModel):
    payload: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload(document_id: str) -> bytes:
    return document_store.get_bytes(document_id) or b""


def _content_hash(document_id: str) -> str:
    return "sha256:" + sha256(_payload(document_id)).hexdigest()


def _content_ref(document_id: str, version_id: str) -> str:
    return f"sourceos-office://wopi-host/{document_id}/versions/{version_id}.odt"


def _storage_uri(document_id: str) -> str:
    return f"sourceos-office://wopi-host/{document_id}.odt"


def _document_record(document_id: str) -> dict[str, object]:
    versions = version_store.list_versions(document_id)
    state = store.get(document_id)
    now = _now()
    return {
        "document_id": document_id,
        "tenant_id": "tenant-demo",
        "owner_id": "user://wopi-demo-owner",
        "storage_uri": _storage_uri(document_id),
        "source_provider": "SOURCEOS",
        "current_format": "odt",
        "canonical_format": "ODF",
        "permissions_ref": "permissions://office/wopi-host-demo",
        "version_head": versions[-1] if versions else f"version-{document_id}-000",
        "editor_binding": "COLLABORA",
        "created_at": state.updated_at if state else now,
        "updated_at": state.updated_at if state else now,
    }


def _session_record(state: SessionState, status: str = "OPEN") -> dict[str, object]:
    return {
        "session_id": state.session_id,
        "document_id": state.document_id,
        "editor_binding": "COLLABORA",
        "mode": "EDIT",
        "participants": [],
        "lock_token": state.lock_token,
        "version_head": f"version-{state.document_id}-{state.version_counter:03d}",
        "status": status,
        "created_at": state.updated_at,
        "updated_at": state.updated_at,
    }


def _version_record(
    *,
    document_id: str,
    version_id: str,
    version_number: int,
    capture_source: str,
    previous_version_id: str | None = None,
    writeback_ref: str | None = None,
) -> dict[str, object]:
    now = _now()
    record: dict[str, object] = {
        "version_id": version_id,
        "document_id": document_id,
        "tenant_id": "tenant-demo",
        "version_number": version_number,
        "content_ref": _content_ref(document_id, version_id),
        "content_hash": _content_hash(document_id),
        "format": "odt",
        "canonical_format": "ODF",
        "source_provider": "SOURCEOS",
        "execution_backend": "COLLABORA",
        "capture_source": capture_source,
        "created_by_ref": "service://wopi-host",
        "receipt_refs": [],
        "semantic_unit_refs": [],
        "created_at": now,
        "labels": {"sourceos.wopi": capture_source.lower().replace("_", "-")},
    }
    if previous_version_id:
        record["previous_version_id"] = previous_version_id
    if writeback_ref:
        record["writeback_ref"] = writeback_ref
    VERSION_RECORDS[version_id] = record
    return record


def _writeback_record(
    *,
    document_id: str,
    state: SessionState,
    version_id: str,
    writeback_id: str,
    base_version_id: str,
    operation: str,
) -> dict[str, object]:
    now = _now()
    record: dict[str, object] = {
        "writeback_id": writeback_id,
        "document_id": document_id,
        "session_id": state.session_id,
        "operation": operation,
        "status": "COMMITTED",
        "base_version_id": base_version_id,
        "result_version_id": version_id,
        "lock_token": state.lock_token,
        "actor_ref": "service://wopi-host",
        "source": "EDITOR_SESSION",
        "execution_backend": "COLLABORA",
        "content_ref": _content_ref(document_id, version_id),
        "content_hash": _content_hash(document_id),
        "receipt_ref": f"receipt://office/wopi-host/{writeback_id}",
        "requested_at": now,
        "committed_at": now,
        "labels": {"sourceos.hot_path": "narrow"},
    }
    WRITEBACK_RECORDS[writeback_id] = record
    return record


def _record_writeback(document_id: str, state: SessionState, operation: str) -> tuple[dict[str, object], dict[str, object]]:
    versions_before = version_store.list_versions(document_id)
    base_version_id = versions_before[-1] if versions_before else f"version-{document_id}-000"
    version_id = f"version-{state.document_id}-{state.version_counter:03d}"
    writeback_id = f"writeback-{state.document_id}-{state.version_counter:03d}"
    version_store.append(document_id, version_id)
    writeback = _writeback_record(
        document_id=document_id,
        state=state,
        version_id=version_id,
        writeback_id=writeback_id,
        base_version_id=base_version_id,
        operation=operation,
    )
    version = _version_record(
        document_id=document_id,
        version_id=version_id,
        version_number=state.version_counter,
        capture_source="WOPI_WRITEBACK",
        previous_version_id=None if base_version_id.endswith("-000") else base_version_id,
        writeback_ref=f"writeback://office/{writeback_id}",
    )
    return version, writeback


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
        "document_record": _document_record(document_id),
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
        "session_record": _session_record(state),
    }


@app.post("/v0/wopi/refresh-lock/{document_id}")
def refresh_lock(document_id: str) -> dict[str, object]:
    state = store.refresh_lock(document_id)
    if state is None:
        return Response(status_code=404)
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "lock_token": state.lock_token,
        "status": "LOCK_REFRESHED",
        "updated_at": state.updated_at,
        "session_record": _session_record(state),
    }


@app.post("/v0/wopi/unlock/{document_id}")
def unlock(document_id: str) -> dict[str, object]:
    state = store.release_lock(document_id)
    if state is None:
        return Response(status_code=404)
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "lock_token": state.lock_token,
        "status": "UNLOCKED",
        "updated_at": state.updated_at,
        "session_record": _session_record(state, status="CLOSED"),
    }


@app.post("/v0/wopi/writeback/{document_id}")
def writeback(document_id: str) -> dict[str, object]:
    state = store.writeback(document_id)
    version, writeback_record = _record_writeback(document_id, state, "WOPI_PUT_FILE")
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "version_id": version["version_id"],
        "status": "WRITTEN",
        "updated_at": state.updated_at,
        "version_record": version,
        "writeback_record": writeback_record,
        "document_record": _document_record(document_id),
        "session_record": _session_record(state, status="SAVING"),
    }


@app.post("/v0/wopi/file-writeback/{document_id}")
def file_writeback(document_id: str) -> dict[str, object]:
    state = file_store.writeback(document_id)
    version, writeback_record = _record_writeback(document_id, state, "WOPI_PUT_FILE")
    return {
        "document_id": state.document_id,
        "session_id": state.session_id,
        "version_id": version["version_id"],
        "status": "WRITTEN",
        "updated_at": state.updated_at,
        "store": "file",
        "version_record": version,
        "writeback_record": writeback_record,
        "document_record": _document_record(document_id),
        "session_record": _session_record(state, status="SAVING"),
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
    version, writeback_record = _record_writeback(document_id, state, "WOPI_PUT_FILE")
    return {
        "document_id": state.document_id,
        "version_id": version["version_id"],
        "status": "WRITTEN",
        "store": "payload",
        "version_record": version,
        "writeback_record": writeback_record,
        "document_record": _document_record(document_id),
        "session_record": _session_record(state, status="SAVING"),
    }


@app.get("/v0/wopi/versions/{document_id}")
def list_versions(document_id: str) -> dict[str, object]:
    return {
        "document_id": document_id,
        "versions": version_store.list_versions(document_id),
    }


@app.get("/v0/wopi/version-records/{document_id}")
def list_version_records(document_id: str) -> dict[str, object]:
    records = [item for item in VERSION_RECORDS.values() if item["document_id"] == document_id]
    records.sort(key=lambda item: int(item["version_number"]))
    return {"document_id": document_id, "version_records": records}


@app.get("/v0/wopi/writeback-records/{document_id}")
def list_writeback_records(document_id: str) -> dict[str, object]:
    records = [item for item in WRITEBACK_RECORDS.values() if item["document_id"] == document_id]
    return {"document_id": document_id, "writeback_records": records}


@app.get("/v0/wopi/payload-metadata/{document_id}")
def payload_metadata(document_id: str):
    metadata = document_store.get_metadata(document_id)
    if metadata is None:
        return Response(status_code=404)
    return metadata


@app.get("/v0/wopi/document-summary/{document_id}")
def document_summary(document_id: str) -> dict[str, object]:
    state = store.get(document_id)
    metadata = document_store.get_metadata(document_id)
    return {
        "document_id": document_id,
        "has_session": state is not None,
        "version_counter": 0 if state is None else state.version_counter,
        "versions": version_store.list_versions(document_id),
        "payload_metadata": metadata,
        "document_record": _document_record(document_id),
        "session_record": _session_record(state) if state else None,
        "version_records": [item for item in VERSION_RECORDS.values() if item["document_id"] == document_id],
        "writeback_records": [item for item in WRITEBACK_RECORDS.values() if item["document_id"] == document_id],
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
