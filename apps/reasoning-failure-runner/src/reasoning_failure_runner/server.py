"""server.py — the chaos/resilience orchestrator HTTP surface.

The runner OWNS experiment definitions (decision #2): it holds suites, runs them against the synthetic cohort,
and returns a resilience rollup. Wiring the active policy to the Capability Membrane for a live experiment window
is Phase 1b; Phase 1a proves the loop mechanics against synthetic targets.

  GET  /healthz                     liveness
  GET  /v1/suites                   the built-in suites (tool-plane empty-200, plausible-wrong, commons regression)
  POST /v1/experiments/run          run a suite (by id or inline) against a task set → ExperimentRollup
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .domain import ExperimentRollup, ExperimentSuite
from .engine import run_experiment
from .suites import BUILTIN_SUITES, SYNTHETIC_TASKS

SERVICE_NAME = "reasoning-failure-runner"
SERVICE_VERSION = "0.2.0"

app = FastAPI(title="Chaos & Resilience Fabric — reasoning-failure-runner", version=SERVICE_VERSION)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": SERVICE_NAME, "version": SERVICE_VERSION, "suites": sorted(BUILTIN_SUITES)}


@app.get("/v1/suites")
def list_suites() -> dict[str, Any]:
    return {"suites": [s.model_dump(by_alias=True) for s in BUILTIN_SUITES.values()]}


class RunRequest(BaseModel):
    suite_id: Optional[str] = None            # run a built-in suite by id …
    suite: Optional[ExperimentSuite] = None   # … or supply one inline
    tasks: Optional[list[dict]] = None        # synthetic cohort; defaults to the built-in task set


@app.post("/v1/experiments/run", response_model=ExperimentRollup)
def run(req: RunRequest) -> ExperimentRollup:
    if req.suite is not None:
        suite = req.suite
    elif req.suite_id is not None:
        suite = BUILTIN_SUITES.get(req.suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"unknown suite_id '{req.suite_id}'")
    else:
        raise HTTPException(status_code=400, detail="provide suite_id or an inline suite")
    tasks = req.tasks if req.tasks is not None else SYNTHETIC_TASKS
    try:
        return run_experiment(suite, tasks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
