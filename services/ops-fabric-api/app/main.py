from __future__ import annotations

from fastapi import FastAPI

from app.models import ActionProposal, WorkloadResourceSample
from app.proposals import build_rightsize_proposal

app = FastAPI(title="ops-fabric-api", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ops-fabric-api"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "ops-fabric-api"}


@app.post("/v1/ops/proposals/rightsize", response_model=ActionProposal)
def rightsize(body: WorkloadResourceSample) -> ActionProposal:
    return build_rightsize_proposal(body)
