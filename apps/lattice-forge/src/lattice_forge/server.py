"""lattice-forge — the governed notebook runtime.

Adapter-based (per the NotebookSurfacePlane design rule: JupyterLab is the
default adapter, NOT the ontology). Two capabilities, one governance discipline:

  1. JupyterLab session broker  — spawn/route a full notebook surface, fronted
     for auth + governed by lattice-studio.
  2. Headless cell execution    — run a cell via nbclient, capture outputs, and
     seal a hash-chained, replayable receipt (the moat).

Fail-closed: FORGE_TOKEN must be set and presented, or protected routes 503/401.
Isolation: this service is deployed to its own `sovereign-runtime` namespace
(default-deny NetworkPolicy, no metadata egress) because it executes user code.
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import adapters, execn, receipts

app = FastAPI(title="lattice-forge", version="0.1.0")

FORGE_TOKEN = os.environ.get("FORGE_TOKEN", "")
JUPYTERLAB_URL = os.environ.get("JUPYTERLAB_URL", "").rstrip("/")
# Browser-facing Lab URL (governed GCE ingress, e.g. https://lab.socioprophet.ai). The forge lives in the
# same namespace as the Lab, so it holds the Lab token and hands an authed user a ready-to-open URL — the
# token only ever reaches a user who already passed the BFF's auth to reach this broker.
JUPYTERLAB_PUBLIC_URL = os.environ.get("JUPYTERLAB_PUBLIC_URL", "").rstrip("/")
JUPYTER_TOKEN = os.environ.get("JUPYTER_TOKEN", "")
DEFAULT_TIMEOUT = int(os.environ.get("FORGE_EXEC_TIMEOUT", "60"))

# in-memory session store (v1). project -> {id -> session}. Persistence = follow-up.
_SESSIONS: dict[str, dict[str, dict]] = {}


def require_token(authorization: str = Header(default="")) -> None:
    """Fail closed: no token configured -> service unavailable; wrong token -> 401."""
    if not FORGE_TOKEN:
        raise HTTPException(status_code=503, detail="forge token not configured (fail-closed)")
    presented = authorization.removeprefix("Bearer ").strip()
    if presented != FORGE_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


class SessionReq(BaseModel):
    project: str
    adapter: str | None = None
    name: str | None = None
    actor: str = "user"


class ExecReq(BaseModel):
    project: str
    code: str
    language: str = "python"
    adapter: str | None = None
    session_id: str | None = None
    actor: str = "user"
    timeout: int = Field(default=0)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "lattice-forge", "kernel_ready": execn.kernel_available()}


@app.get("/v1/adapters")
def list_adapters(_: None = Depends(require_token)) -> dict:
    return {"default": adapters.DEFAULT_ADAPTER, "adapters": adapters.ADAPTERS}


@app.post("/v1/session")
def create_session(req: SessionReq, _: None = Depends(require_token)) -> dict:
    try:
        name, meta = adapters.resolve(req.adapter)
    except KeyError:
        raise HTTPException(status_code=422, detail=f"unknown adapter: {req.adapter}")
    sid = receipts.new_id()
    # a jupyterlab/zeppelin adapter is a brokered surface: point at the runtime URL.
    # brokered surfaces (jupyterlab/zeppelin) → a browser-openable URL. Prefer the public ingress; append the
    # Lab token so an authed user lands straight in. Fall back to the in-cluster URL (BFF-proxy path) if no edge.
    if meta["mode"] == "session" and JUPYTERLAB_PUBLIC_URL:
        url = f"{JUPYTERLAB_PUBLIC_URL}/lab" + (f"?token={JUPYTER_TOKEN}" if JUPYTER_TOKEN else "")
    elif meta["mode"] == "session" and JUPYTERLAB_URL:
        url = f"{JUPYTERLAB_URL}/lab/tree/{req.project}"
    else:
        url = None
    session = {
        "id": sid, "project": req.project, "adapter": name, "role": meta["role"],
        "mode": meta["mode"], "kernel": meta["kernels"][0], "name": req.name or f"{name} session",
        "status": "ready", "url": url, "actor": req.actor,
    }
    _SESSIONS.setdefault(req.project, {})[sid] = session
    return session


@app.get("/v1/sessions")
def list_sessions(project: str, _: None = Depends(require_token)) -> dict:
    return {"project": project, "sessions": list(_SESSIONS.get(project, {}).values())}


@app.delete("/v1/session/{sid}")
def delete_session(sid: str, project: str, _: None = Depends(require_token)) -> dict:
    _SESSIONS.get(project, {}).pop(sid, None)
    execn.shutdown(sid)   # tear down the session's persistent kernel
    return {"ok": True}


@app.post("/v1/execute")
def execute(req: ExecReq, _: None = Depends(require_token)) -> dict:
    try:
        name, meta = adapters.resolve(req.adapter)
    except KeyError:
        raise HTTPException(status_code=422, detail=f"unknown adapter: {req.adapter}")
    runtime = meta["kernels"][0]
    # persistent per-session kernel → cells share state (a real notebook, not one-shot cells)
    session_id = req.session_id or f"{req.project}:default"
    try:
        result = execn.run_cell(req.code, req.language, req.timeout or DEFAULT_TIMEOUT, session_id)
        degraded = None
    except execn.ForgeUnavailable as e:
        # honest degradation — never fake a result. Still seals a receipt of the attempt.
        result = {"status": "degraded", "outputs": [], "error": str(e)}
        degraded = str(e)

    receipt = receipts.seal(
        req.project, adapter=name, language=req.language, runtime=runtime,
        code=req.code, outputs=result["outputs"], status=result["status"], actor=req.actor,
    )
    return {
        "status": result["status"], "outputs": result["outputs"],
        "error": result.get("error"), "degraded": degraded,
        "receipt": receipt, "adapter": name, "runtime": runtime,
    }


@app.get("/v1/receipts")
def get_receipts(project: str, _: None = Depends(require_token)) -> dict:
    ch = receipts.chain(project)
    return {"project": project, "count": len(ch), "receipts": ch}
