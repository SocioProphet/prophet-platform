from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .materialize_bound_bundle import materialize_bound_bundle
from ...evidence-receipts.app.store import get_bundle, platform_state_root

app = FastAPI(title="Prophet Platform Workflow Local Runner Bundle Materializer", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "workflow-local-runner-materialize"}


@app.post("/v1/bundles/{service}/{correlation_id}/materialize")
def materialize(service: str, correlation_id: str) -> dict[str, str]:
    bundle = get_bundle(service=service, correlation_id=correlation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="receipt bundle not found")

    out_path = materialize_bound_bundle(
        service=service,
        correlation_id=correlation_id,
        workflow_run=bundle["payload"]["workflow_run"],
        execution_envelope=bundle["payload"]["execution_envelope"],
        event_doc=bundle["event"],
        receipt_doc=bundle["receipt"],
        payload_doc=bundle["payload"],
        catalog_entry=bundle["catalog_entry"],
        platform_root=platform_state_root(),
    )

    return {
        "service": service,
        "correlation_id": correlation_id,
        "bundle_ref": f"file://{Path(out_path).resolve()}",
    }
