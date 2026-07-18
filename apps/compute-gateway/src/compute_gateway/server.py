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

from pydantic import BaseModel

from . import engine, planner, receipts, registry, zerotrust
from .contract import ComputeRequest, ComputeResult

app = FastAPI(title="compute-gateway", version="0.1.0")

GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")


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
    """One governed door for every kind of compute. Unknown kind/backend is a 422
    (client error); everything else the engine resolves, gates (entitlement +
    zero-trust grant), memoizes, routes (or, for a `workflow`, orchestrates a DAG
    of governed sub-computes), seals, attests, and writes provenance for."""
    try:
        registry.resolve(req.kind, req.backend)
    except registry.UnknownKind:
        raise HTTPException(status_code=422, detail=f"unknown compute kind: {req.kind}")
    except registry.UnknownBackend as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await engine.execute(req)


class PlanRequest(BaseModel):
    capabilities: list[str] = []
    project: str = "default"
    intent: str | None = None
    entitlement: str | None = None


@app.post("/v1/plan")
def plan_view(req: PlanRequest, _: None = Depends(require_token)) -> dict:
    """Plan a governed workflow over the capability registry (layer 6 — the
    registry as an agent action space). A PREVIEW: returns a runnable `workflow`
    spec + per-step entitlement/warrant, but executes nothing. Planning is free;
    hand `plan` to POST /v1/compute to run it under full governance."""
    return planner.plan(capabilities=req.capabilities, project=req.project,
                        intent=req.intent, entitlement=req.entitlement)


@app.get("/v1/capability-registry")
def capability_registry_view(_: None = Depends(require_token)) -> dict:
    """The gateway declared to OUR zero-trust kernel — every compute kind is an MCP
    tool with an effect, danger class, and trust hints. Conforms to
    mcp-a2a-zero-trust `capability_registry.schema.json` (validated at startup)."""
    return zerotrust.capability_registry()


@app.get("/v1/attestation")
def attestation_view(project: str = "default", receipt_id: str | None = None,
                     _: None = Depends(require_token)) -> dict:
    """AttestationBundle(s) over sealed receipts — the kernel/agentplane consume
    these to gate downstream actions on proof. `cosign_valid` reflects a verifying
    Ed25519 signature over the in-toto Statement."""
    ch = receipts.chain(project)
    if receipt_id:
        match = next((r for r in ch if r.id == receipt_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"no receipt {receipt_id} in project {project}")
        return {"project": project, "attestation": zerotrust.attestation_bundle(match)}
    return {"project": project, "count": len(ch),
            "attestations": [zerotrust.attestation_bundle(r) for r in ch]}


@app.get("/v1/receipts")
def receipts_view(project: str = "default", _: None = Depends(require_token)) -> dict:
    ch = receipts.chain(project)
    return {"project": project, "count": len(ch), "receipts": [r.model_dump() for r in ch]}


@app.get("/v1/receipts/verify")
def receipts_verify(project: str = "default", _: None = Depends(require_token)) -> dict:
    return receipts.verify(project)
