from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from store import build_subject_readout

app = FastAPI(title="liberty-stack-combined-readout", version="0.1.0")


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    return json.loads(file_path.read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "liberty-stack-combined-readout"}


@app.get("/v1/liberty-stack/readout")
def readout(
    receipt: str | None = Query(None, description="Optional path to receipt JSON"),
    verification: str | None = Query(None, description="Optional path to verification JSON"),
    event: list[str] | None = Query(None, description="Optional path(s) to event JSON"),
    state_root: str | None = Query(None, description="Optional root directory to search for receipt JSON"),
    subject_ref: str | None = Query(None, description="Optional subject to resolve from local state"),
) -> dict[str, Any]:
    if receipt is not None:
        receipt_payload = _load_json(receipt)
        verification_payload = _load_json(verification) if verification else None
        event_payloads = [_load_json(item) for item in (event or [])]
        return {
            "subject_ref": receipt_payload.get("subject_ref"),
            "action": receipt_payload.get("action"),
            "status": receipt_payload.get("status"),
            "evidence_bundle_ref": receipt_payload.get("evidence_bundle_ref"),
            "verification": verification_payload,
            "events": event_payloads,
        }

    if state_root is not None and subject_ref is not None:
        payload = build_subject_readout(state_root, subject_ref)
        if payload is None:
            raise HTTPException(status_code=404, detail="subject not found")
        return payload

    raise HTTPException(status_code=400, detail="provide either receipt=... or state_root=... with subject_ref=...")
