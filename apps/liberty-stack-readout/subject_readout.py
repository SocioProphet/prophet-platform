from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from store import build_subject_readout

app = FastAPI(title="liberty-stack-subject-readout", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "liberty-stack-subject-readout"}


@app.get("/v1/liberty-stack/by-subject")
def by_subject(
    state_root: str = Query(..., description="Root directory to search for receipt JSON"),
    subject_ref: str = Query(..., description="Subject to resolve from local state"),
) -> dict:
    payload = build_subject_readout(state_root, subject_ref)
    if payload is None:
        raise HTTPException(status_code=404, detail="subject not found")
    return payload
