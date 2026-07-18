"""compute-gateway — one governed door for every kind of compute.

POST /v1/compute takes a ComputeRequest, gates it (auth + uniform entitlement),
routes it to the owning backend adapter, seals the universal hash-chained
receipt, types the output's warrant, and writes the run's provenance subgraph
back to the graph. Notebook and graph queries go through the exact same path —
the walking skeleton of "any compute, one contract".
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException

from . import adapters, receipts, registry
from .contract import ComputeRequest, ComputeResult

app = FastAPI(title="compute-gateway", version="0.1.0")

GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")
WRITE_PROVENANCE = os.getenv("GATEWAY_WRITE_PROVENANCE", "true").lower() == "true"


def require_token(authorization: str = Header(default="")) -> None:
    if not GATEWAY_TOKEN:
        raise HTTPException(status_code=503, detail="gateway token not configured (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "compute-gateway", "kinds": list(registry.KINDS)}


@app.get("/v1/contract")
def contract() -> dict:
    """The contract itself, as JSON schema — the spine everything conforms to."""
    return {"request": ComputeRequest.model_json_schema(),
            "result": ComputeResult.model_json_schema()}


@app.get("/v1/registry")
def registry_view(project: str = "default", entitlement: str | None = None,
                  _: None = Depends(require_token)) -> dict:
    return {"project": project, "kinds": registry.catalog(project, entitlement)}


@app.post("/v1/compute", response_model=ComputeResult)
async def compute(req: ComputeRequest, _: None = Depends(require_token)) -> ComputeResult:
    # 1) resolve kind + backend
    try:
        kind, _def, backend = registry.resolve(req.kind, req.backend)
    except registry.UnknownKind:
        raise HTTPException(status_code=422, detail=f"unknown compute kind: {req.kind}")
    except registry.UnknownBackend as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 2) the UNIFORM pay-gate — one gate for all compute (like Databricks/Foundry,
    #    but sovereign + per-kind/per-backend). Fail-closed with an honest 402.
    if not registry.entitled(req.project, kind, backend, req.entitlement):
        return ComputeResult(
            status="entitlement_required", kind=kind, backend=backend,
            epistemic_status=registry.epistemic_for(kind), entitlement_required=True,
            message=f"compute '{kind}:{backend}' is a provisioned service — no entitlement for "
                    f"project '{req.project}' (set COMPUTE_ENTITLEMENTS)")

    # 3) route to the backend adapter (raw outputs; no receipt yet)
    raw = await adapters.dispatch(kind, backend, req.spec, req.project, req.session)
    epistemic = registry.epistemic_for(kind)
    status = raw["status"]

    # 4) SEAL the universal receipt — the same for a cell, a query, anything
    receipt = receipts.seal(
        req.project, kind=kind, backend=backend, runtime=raw["runtime"],
        inputs=req.spec, outputs=[o.model_dump() for o in raw["outputs"]],
        status=status, actor=req.actor, epistemic_status=epistemic)

    # 5) provenance subgraph — compute + knowledge, one object model
    delta = adapters.build_delta(req.project, kind, backend, receipt.id, epistemic)
    if WRITE_PROVENANCE and status == "ok":
        delta.written = await adapters.write_provenance(delta)

    return ComputeResult(
        status=status, kind=kind, backend=backend, epistemic_status=epistemic,
        outputs=raw["outputs"], receipt=receipt, graph_delta=delta,
        error=raw.get("error"), degraded=raw.get("degraded"))


@app.get("/v1/receipts")
def receipts_view(project: str = "default", _: None = Depends(require_token)) -> dict:
    ch = receipts.chain(project)
    return {"project": project, "count": len(ch), "receipts": [r.model_dump() for r in ch]}


@app.get("/v1/receipts/verify")
def receipts_verify(project: str = "default", _: None = Depends(require_token)) -> dict:
    return receipts.verify(project)
