"""Agentic OS API — the coordination service for the agentic operating system.

Serves the canonical agentic-OS objects (Opportunity / AgentPod / ReadinessScore
/ CaptureCadence) the cockpit console renders and the pods coordinate against.
Objects conform to the sourceos-spec agentic-OS contract and compose over
prophet-workspace (workrooms) + prophet-mesh (choir + estate graph). Read-only
seed for now; a live registry adapter resolves the same URNs from the workspace
and estate graph.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .data import CADENCE, OPPORTUNITIES, PODS, READINESS, opp_slug

app = FastAPI(title="Prophet Platform Agentic OS API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "agentic-os-api", "objectives": len(OPPORTUNITIES), "pods": len(PODS)}


@app.get("/opportunities")
def list_opportunities() -> dict:
    return {"opportunities": OPPORTUNITIES, "count": len(OPPORTUNITIES)}


@app.get("/opportunities/{slug}")
def get_opportunity(slug: str) -> dict:
    opp = next((o for o in OPPORTUNITIES if opp_slug(o) == slug), None)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"opportunity {slug!r} not found")
    return {"opportunity": opp, "readiness": READINESS.get(slug), "cadence": CADENCE}


@app.get("/pods")
def list_pods() -> dict:
    return {"pods": PODS, "count": len(PODS)}


@app.get("/cadence")
def get_cadence() -> dict:
    return CADENCE
