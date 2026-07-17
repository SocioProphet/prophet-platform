"""GRL-mesh service — the sovereign, opt-in learning-signal mesh.

Carries Graph-RL reward signals between nodes so the community learns together, over the same envelope
as the open-chat commons: opt-in, per-node write token, sovereign-id pseudonym, and only redacted
sufficient statistics (mean reward + count per coarse context bucket) — never raw contexts or data.

Endpoints:
  GET  /healthz
  POST /grl/publish            { policy, observations:[{action,context_bucket,reward}] }  (token-gated)
  GET  /grl/prior?policy=      the aggregated community prior a node pulls to warm-start
  GET  /grl/policies           policies with signal
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .aggregator import MeshAggregator

# Per-node write token. Fail-CLOSED: if unset, publish is refused (same posture as commons-search) so a
# misconfigured mesh never silently accepts unauthenticated signals. Reads (the prior) stay open — it is
# aggregate, non-identifying statistics.
PUBLISH_TOKEN = os.getenv("GRL_MESH_TOKEN", "")
MAX_OBS = int(os.getenv("GRL_MESH_MAX_OBS", "500"))

app = FastAPI(title="grl-mesh", version="0.1.0")
_agg = MeshAggregator()


class PublishRequest(BaseModel):
    policy: str
    observations: list[dict[str, Any]]


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "grl-mesh", "publish_gated": bool(PUBLISH_TOKEN)}


@app.post("/grl/publish")
def publish(
    req: PublishRequest,
    authorization: str = Header(default=""),
    x_sovereign_id: str = Header(default="anon"),
) -> dict[str, Any]:
    if not PUBLISH_TOKEN:
        raise HTTPException(status_code=503, detail="mesh publish disabled: GRL_MESH_TOKEN unset (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != PUBLISH_TOKEN:
        raise HTTPException(status_code=401, detail="invalid publish token")
    if not req.policy or not isinstance(req.observations, list):
        raise HTTPException(status_code=400, detail="policy and observations[] required")
    accepted = _agg.publish(req.policy, req.observations[:MAX_OBS], sovereign_id=x_sovereign_id or "anon")
    return {"ok": True, "accepted": accepted, "policy": req.policy}


@app.get("/grl/prior")
def prior(policy: str) -> dict[str, Any]:
    return _agg.prior(policy)


@app.get("/grl/policies")
def policies() -> dict[str, Any]:
    return {"policies": _agg.policies(), "total_observations": _agg.published}
