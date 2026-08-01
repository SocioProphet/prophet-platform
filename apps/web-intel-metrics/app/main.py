from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .store import EVENT_TYPES, SERVICE, get_bundle, list_recent

app = FastAPI(title="Prophet Platform Web Intelligence Metrics", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": SERVICE}


@app.get("/v1/web-intel/event-types")
def event_types() -> dict:
    return {"service": SERVICE, "event_types": EVENT_TYPES}


@app.get("/v1/web-intel/recent")
def recent(limit: int = Query(20, ge=1, le=200)) -> dict:
    return {"service": SERVICE, "items": list_recent(limit=limit)}


@app.get("/v1/web-intel/by-subject/{subject}")
def by_subject(subject: str, limit: int = Query(20, ge=1, le=200)) -> dict:
    # Symmetric: works for our own domains and for competitors alike.
    return {"service": SERVICE, "subject": subject, "items": list_recent(limit=limit, subject=subject)}


@app.get("/v1/web-intel/{correlation_id}")
def detail(correlation_id: str) -> dict:
    bundle = get_bundle(correlation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="bundle not found")
    return bundle
