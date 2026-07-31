"""Cloud-Twin as a Service — prophet-platform.

Serves the cybernetic-agentic-genesis Twin as a hosted API: submit a GenesisSeed,
get back a verified Twin whose K3 lifecycle is a replayable TwinEventEnvelope
stream. Read-only/no-op skeleton (genesis plan Phase-1); world-changing adapters
are gated behind later phases. Objects conform to the canonical sourceos-spec
schemas (GenesisSeed, TwinEventEnvelope).
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from .twin import SeedValidationError, TwinRegistry

app = FastAPI(title="Prophet Platform Cloud-Twin", version="0.1.0")
_registry = TwinRegistry()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "cloud-twin", "twins": _registry.count()}


@app.post("/twins", status_code=201)
def create_twin(seed: dict[str, Any], actor_id: str = "user:anonymous") -> dict:
    """Instantiate a verified Twin from a GenesisSeed (fail closed on a bad seed)."""
    try:
        twin = _registry.instantiate(seed, actor_id)
    except SeedValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"twin_id": twin.twin_id, "state": twin.state, "events": twin.events}


@app.get("/twins/{twin_id:path}/events")
def get_twin_events(twin_id: str) -> dict:
    """The replayable TwinEventEnvelope stream that reconstructs the lifecycle.

    Declared before the catch-all so the greedy :path converter does not swallow
    the /events suffix.
    """
    twin = _registry.get(twin_id)
    if twin is None:
        raise HTTPException(status_code=404, detail=f"twin not found: {twin_id}")
    return {"twin_id": twin.twin_id, "events": twin.events, "count": len(twin.events)}


@app.get("/twins/{twin_id:path}")
def get_twin(twin_id: str) -> dict:
    twin = _registry.get(twin_id)
    if twin is None:
        raise HTTPException(status_code=404, detail=f"twin not found: {twin_id}")
    return {"twin_id": twin.twin_id, "state": twin.state, "seed": twin.seed, "events": twin.events}
