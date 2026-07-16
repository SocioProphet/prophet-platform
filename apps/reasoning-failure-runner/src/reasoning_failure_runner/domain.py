"""domain.py — the chaos/resilience experiment model.

Generalises the existing perturbation-suite vocabulary (suiteId / perturbationId / invariant, see
examples/exactness-perturbations.json) to the five injection planes of CHAOS_RESILIENCE_FABRIC_V0.md. An
exactness perturbation is just ``plane="tool", invariant="exactString"`` — the existing examples become the
first suite, not throwaway.

Everything here is provider-neutral and deterministic: no LLM-as-judge, synthetic cohort only (Phase 1a).
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "prophet-platform.resilience-receipt.v0.2"


class Plane(str, Enum):
    tool = "tool"
    model = "model"
    retrieval = "retrieval"
    swarm = "swarm"
    time = "time"


class Verdict(str, Enum):
    """The Assay ternary — the chaos scorecard. bad+unflagged = the silent failure."""
    ok = "ok"       # invariant held (unaffected or recovered)
    sad = "sad"     # degraded but FLAGGED (errored / abstained) — impaired, not wrong
    bad = "bad"     # WRONG output


class Fault(BaseModel):
    kind: str = Field(..., description="e.g. empty-200 | timeout | plausible-wrong | truncate | poisoned-chunk")
    params: dict[str, Any] = Field(default_factory=dict)


class Cohort(BaseModel):
    roles: list[str] = Field(..., min_length=1, description="swarm AGENT_ROLES; REQUIRED — no cohort ⇒ no run")
    session_class: str = Field("ephemeral", description="ephemeral | shadow — never live/side-effecting")
    sample_rate: float = Field(1.0, ge=0.0, le=1.0)


class SteadyState(BaseModel):
    sli: str = Field("goal_completion_rate")
    floor: float = Field(0.9, ge=0.0, le=1.0)


class Perturbation(BaseModel):
    perturbation_id: str = Field(..., alias="perturbationId")
    description: str = ""
    plane: Plane = Plane.tool
    fault: Fault
    invariant: str = Field("exactString", description="the silent-failure oracle: exactString|grounded|non-fabricated|revoked-not-served")

    model_config = {"populate_by_name": True}


class ExperimentSuite(BaseModel):
    suite_id: str = Field(..., alias="suiteId")
    suite_type: str = Field("resilience", alias="suiteType")
    cohort: Cohort
    steady_state: SteadyState = Field(default_factory=SteadyState, alias="steadyState")
    target: str = Field("naive", description="synthetic target adapter name (Phase 1a)")
    perturbations: list[Perturbation] = Field(..., min_length=1)

    model_config = {"populate_by_name": True}


class RunOutcome(BaseModel):
    """One agent run against one task, under (or without) a fault."""
    task_id: str
    output: str
    flagged: bool = Field(False, description="did the run signal a problem (error/abstain/low-confidence)")
    steps: int = Field(1, description="tool/reasoning steps; >1 under a fault ⇒ a recovery attempt")


class ResilienceReceipt(BaseModel):
    schema_version: str = SCHEMA_VERSION
    record_type: str = "ResilienceReceipt"
    experiment_id: str
    suite_id: str
    perturbation_id: str
    plane: Plane
    fault: Fault
    task_id: str
    invariant: str
    verdict: Verdict
    recovered: bool
    recovery_steps: int
    silent_failure: bool = Field(..., description="⚑ wrong output that was NOT flagged — the metric infra chaos can't see")
    issued_at: str
    receipt_hash: str = ""


class ExperimentRollup(BaseModel):
    schema_version: str = SCHEMA_VERSION
    record_type: str = "ExperimentRollup"
    experiment_id: str
    suite_id: str
    n: int
    completion_before: float
    completion_after: float
    steady_state_floor: float
    slo_held: bool
    silent_failure_rate: float
    verdicts: dict[str, int]
    recovered_rate: float
    passed: bool = Field(..., description="slo_held AND silent_failure_rate == 0")
    issued_at: str
    receipts: list[ResilienceReceipt] = Field(default_factory=list)
