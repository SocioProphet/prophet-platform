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

from . import adapters, execn, receipts, schedules

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


class ScheduleReq(BaseModel):
    project: str
    name: str
    code: str
    language: str = "python"
    adapter: str | None = None
    session_id: str | None = None
    interval_seconds: int
    actor: str = "user"


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


def _run_and_seal(project: str, code: str, language: str, adapter_name: str,
                  runtime: str, session_id: str, timeout: int, actor: str) -> tuple[dict, str | None, dict]:
    """Run a cell through the governed path and seal its receipt.

    The single choke-point shared by interactive `/v1/execute` and the scheduled
    `/v1/run-due` tick: identical execution, identical degradation, identical seal —
    a scheduled job is exactly as proof-carrying as a human-triggered one.
    """
    try:
        result = execn.run_cell(code, language, timeout or DEFAULT_TIMEOUT, session_id)
        degraded = None
    except execn.ForgeUnavailable as e:
        # honest degradation — never fake a result. Still seals a receipt of the attempt.
        result = {"status": "degraded", "outputs": [], "error": str(e)}
        degraded = str(e)
    receipt = receipts.seal(
        project, adapter=adapter_name, language=language, runtime=runtime,
        code=code, outputs=result["outputs"], status=result["status"], actor=actor,
    )
    return result, degraded, receipt


@app.post("/v1/execute")
def execute(req: ExecReq, _: None = Depends(require_token)) -> dict:
    try:
        name, meta = adapters.resolve(req.adapter)
    except KeyError:
        raise HTTPException(status_code=422, detail=f"unknown adapter: {req.adapter}")
    runtime = meta["kernels"][0]
    # persistent per-session kernel → cells share state (a real notebook, not one-shot cells)
    session_id = req.session_id or f"{req.project}:default"
    result, degraded, receipt = _run_and_seal(
        req.project, req.code, req.language, name, runtime, session_id, req.timeout, req.actor,
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


@app.get("/v1/receipts/verify")
def verify_receipts(project: str, _: None = Depends(require_token)) -> dict:
    """Re-prove the project's receipt chain (tamper-evidence, programmatically).

    Recomputes every receipt id from its body and re-walks every prev-link, so a
    single mutated field or a broken link fails verification with `broken_at`
    naming the earliest compromised receipt — the moat, made checkable.
    """
    return {"project": project, **receipts.verify(project)}


@app.get("/v1/stats")
def stats(project: str, _: None = Depends(require_token)) -> dict:
    """Read-only forge introspection for the Operations surface.

    Cheap and side-effect-free: live kernel count for the project, its sealed
    receipt-chain length, the registered adapters, and whether a real execution
    kernel is available. Nothing here mutates state or touches a kernel.
    """
    return {
        "project": project,
        "sessions": execn.live_kernels(project),
        "receipts": len(receipts.chain(project)),
        "adapters": list(adapters.ADAPTERS),
        "kernel_ready": execn.kernel_available(),
    }


@app.post("/v1/schedule")
def create_schedule(req: ScheduleReq, _: None = Depends(require_token)) -> dict:
    """Register a recurring governed job. The CronJob fires it via /v1/run-due."""
    if req.adapter is not None and req.adapter not in adapters.ADAPTERS:
        raise HTTPException(status_code=422, detail=f"unknown adapter: {req.adapter}")
    if req.interval_seconds < schedules.MIN_INTERVAL_SECONDS:
        raise HTTPException(
            status_code=422,
            detail=f"interval_seconds must be >= {schedules.MIN_INTERVAL_SECONDS}",
        )
    return schedules.create(
        req.project, req.name, req.code, req.interval_seconds,
        language=req.language, adapter=req.adapter, session_id=req.session_id,
    )


@app.get("/v1/schedules")
def list_schedules(project: str, _: None = Depends(require_token)) -> dict:
    sch = schedules.list(project)
    return {"project": project, "count": len(sch), "schedules": sch}


@app.delete("/v1/schedule/{sid}")
def delete_schedule(sid: str, project: str, _: None = Depends(require_token)) -> dict:
    return {"ok": schedules.delete(sid)}


@app.post("/v1/run-due")
def run_due(_: None = Depends(require_token)) -> dict:
    """Run every due schedule NOW — the endpoint the Kubernetes CronJob ticks.

    Each due schedule takes the same governed path as an interactive cell: run →
    seal a receipt (degraded if the kernel is down, never faked) → advance next_run.
    """
    ran: list[dict] = []
    for s in schedules.due():
        try:
            name, meta = adapters.resolve(s["adapter"])
        except KeyError:
            # adapter went away since the schedule was created — record, don't crash.
            schedules.mark_ran(s["id"], "error")
            ran.append({"id": s["id"], "status": "error", "receipt": None})
            continue
        runtime = meta["kernels"][0]
        result, degraded, receipt = _run_and_seal(
            s["project"], s["code"], s["language"], name, runtime,
            s["session_id"], DEFAULT_TIMEOUT, "scheduler",
        )
        schedules.mark_ran(s["id"], result["status"])
        ran.append({"id": s["id"], "status": result["status"],
                    "degraded": degraded, "receipt": receipt["id"]})
    return {"ran": [r["id"] for r in ran], "count": len(ran), "runs": ran}
