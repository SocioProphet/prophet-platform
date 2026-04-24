from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.models import ActionProposal, SearchRecord, TelemetryEvent, WorkloadResourceSample
from app.proposals import build_rightsize_proposal
from app.store import store

app = FastAPI(title="ops-fabric-api", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ops-fabric-api"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "ops-fabric-api"}


@app.post("/v1/ops/events", response_model=TelemetryEvent)
def add_event(body: TelemetryEvent) -> TelemetryEvent:
    return store.add_event(body)


@app.get("/v1/ops/events", response_model=list[TelemetryEvent])
def list_events() -> list[TelemetryEvent]:
    return store.list_events()


@app.post("/v1/ops/proposals/rightsize", response_model=ActionProposal)
def rightsize(body: WorkloadResourceSample) -> ActionProposal:
    proposal = build_rightsize_proposal(body)
    return store.add_proposal(proposal)


@app.get("/v1/ops/proposals", response_model=list[ActionProposal])
def list_proposals() -> list[ActionProposal]:
    return store.list_proposals()


@app.get("/v1/ops/proposals/{proposal_id}", response_model=ActionProposal)
def get_proposal(proposal_id: str) -> ActionProposal:
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return proposal


@app.get("/v1/ops/search-records", response_model=list[SearchRecord])
def search_records() -> list[SearchRecord]:
    return store.search_records()
