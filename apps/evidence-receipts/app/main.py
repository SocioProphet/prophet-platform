from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .store import get_bundle, list_recent_bundles, list_services, read_catalog_entries

app = FastAPI(title="Prophet Platform Evidence Receipts", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "evidence-receipts"}


@app.get("/v1/services")
def services() -> dict:
    return {"services": list_services()}


@app.get("/v1/receipts/recent")
def recent_receipts(service: str = Query(...), limit: int = Query(20, ge=1, le=200)) -> dict:
    return {
        "service": service,
        "items": list_recent_bundles(service=service, limit=limit),
    }


@app.get("/v1/receipts/{service}/{correlation_id}")
def receipt_bundle(service: str, correlation_id: str) -> dict:
    bundle = get_bundle(service=service, correlation_id=correlation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="receipt bundle not found")
    return bundle


@app.get("/v1/catalog/recent")
def recent_catalog(service: str = Query(...), limit: int = Query(20, ge=1, le=200)) -> dict:
    return {
        "service": service,
        "items": read_catalog_entries(service=service, limit=limit),
    }
