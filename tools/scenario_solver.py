#!/usr/bin/env python3
"""Scenario solver — Ecosystem Simulation Substrate, Wave 2 (Layer B).

Builds on the merged Wave-1 identification spine (`causal_identification`). Layer
A decides *may we claim this*; this is Layer B — *what is the value* — and it runs
**only** on an estimand Layer A has cleared (enforced via `gate`).

Wave-2 guarantees (spec §4, §7, §12):
  * No point estimate for an unidentified estimand — refuse, return non-causal
    bounds + the blocking structure + the measurement that would identify it.
  * Every solved output is a **distribution** carrying propagated parameter
    uncertainty — never a single number.
  * Certified scenarios are **content-addressed** over
    {graph_snapshot_hash, intervention_set, solver_version, assumption_set,
     reaction_level, parameter_vintage, seed} and **replay bit-identically**.
  * Competitor reaction level is declared; L0 (static competitors) is labelled a
    bound, never a forecast.
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
from dataclasses import dataclass, field
from typing import Callable, Optional

from causal_identification import Dag, IdentificationReport, gate, identify

SOLVER_VERSION = "scenario_solver/0.2.0"
_DEFAULT_SAMPLES = 512

# Reaction levels (spec §6). L0 is a bound, never sold as a forecast.
REACTION_LEVELS = {"L0", "L1", "L2", "L3"}


@dataclass
class ParameterFact:
    """A model parameter as a fact: a value with uncertainty and provenance."""

    name: str
    value: float
    interval: tuple[float, float]  # (lo, hi) — parameter uncertainty
    n: int
    provenance: str
    epistemic_level: str
    as_of: str

    def sample(self, rng: random.Random) -> float:
        lo, hi = self.interval
        return self.value if hi <= lo else rng.uniform(lo, hi)


@dataclass
class ScenarioSpec:
    """A scenario: an estimand, an intervention, and the parameters it needs."""

    estimand_id: str
    dag: Dag
    treatment: str
    outcome: str
    intervention: dict[str, float]  # e.g. {"magnitude": -0.08}
    parameters: dict[str, ParameterFact]
    graph_snapshot_hash: str
    parameter_vintage: str
    reaction_level: str = "L0"
    assumption_set: frozenset[str] = frozenset()
    seed: int = 0
    n_samples: int = _DEFAULT_SAMPLES


@dataclass
class Distribution:
    """A scenario output distribution (never a scalar)."""

    mean: float
    p05: float
    p50: float
    p95: float
    n_samples: int


@dataclass
class ScenarioResult:
    content_address: str
    estimand_id: str
    identification_status: str
    reaction_level: str
    refused: bool
    adjustment_set: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    distribution: Optional[Distribution] = None
    label: Optional[str] = None  # e.g. "upper_bound_on_own_move" for L0
    bounds: Optional[tuple[float, float]] = None
    blocking_structure: list[str] = field(default_factory=list)
    measurement_to_identify: list[str] = field(default_factory=list)


def _default_propagation(sample: dict[str, float], intervention: dict[str, float], reaction_level: str) -> float:
    """Model-agnostic default transfer: magnitude x elasticity, damped by reaction.

    Real solvers (discrete-event / choice / best-response) plug in via the
    `propagation` argument; this default just exercises uncertainty propagation.
    L0 holds competitors static (no damping) → an upper bound on the own-move effect.
    """
    magnitude = intervention.get("magnitude", 0.0)
    elasticity = sample.get("elasticity", 1.0)
    reaction = 0.0 if reaction_level == "L0" else sample.get("competitor_reaction", 0.0)
    return magnitude * elasticity * (1.0 - reaction)


def content_address(spec: ScenarioSpec) -> str:
    """Content address over the certifying inputs (spec §7). Deterministic."""
    payload = {
        "graph_snapshot_hash": spec.graph_snapshot_hash,
        "intervention_set": spec.intervention,
        "solver_version": SOLVER_VERSION,
        "assumption_set": sorted(spec.assumption_set),
        "reaction_level": spec.reaction_level,
        "parameter_vintage": spec.parameter_vintage,
        "seed": spec.seed,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _bounds(spec: ScenarioSpec, propagation: Callable) -> tuple[float, float]:
    """Non-causal interval bounds from parameter extremes (for the refusal path)."""
    lows = {k: p.interval[0] for k, p in spec.parameters.items()}
    highs = {k: p.interval[1] for k, p in spec.parameters.items()}
    a = propagation(lows, spec.intervention, spec.reaction_level)
    b = propagation(highs, spec.intervention, spec.reaction_level)
    return (min(a, b), max(a, b))


def solve(spec: ScenarioSpec, *, propagation: Callable = _default_propagation) -> ScenarioResult:
    """Identify, then (only if cleared) propagate parameter uncertainty."""
    if spec.reaction_level not in REACTION_LEVELS:
        raise ValueError(f"unknown reaction_level {spec.reaction_level!r}")

    report: IdentificationReport = identify(
        spec.dag, spec.treatment, spec.outcome, spec.estimand_id,
        assume_unconfounded=set(spec.assumption_set),
    )
    addr = content_address(spec)

    if not report.clearable:
        # REFUSE the point estimate. Return non-causal bounds + what to measure.
        return ScenarioResult(
            content_address=addr,
            estimand_id=spec.estimand_id,
            identification_status=report.status,
            reaction_level=spec.reaction_level,
            refused=True,
            bounds=_bounds(spec, propagation),
            blocking_structure=report.blocking_structure,
            measurement_to_identify=report.measurement_to_identify,
            label="non_causal_bounds_only",
        )

    # Cleared: Monte-Carlo propagate parameter uncertainty (deterministic per seed).
    def _run() -> list[float]:
        rng = random.Random(spec.seed)
        out: list[float] = []
        for _ in range(spec.n_samples):
            sample = {name: spec.parameters[name].sample(rng) for name in sorted(spec.parameters)}
            out.append(propagation(sample, spec.intervention, spec.reaction_level))
        return out

    samples = gate(report, _run)  # Layer-B runs only through the Layer-A gate
    samples.sort()
    dist = Distribution(
        mean=statistics.fmean(samples),
        p05=samples[max(0, int(0.05 * (len(samples) - 1)))],
        p50=samples[int(0.50 * (len(samples) - 1))],
        p95=samples[int(0.95 * (len(samples) - 1))],
        n_samples=len(samples),
    )
    return ScenarioResult(
        content_address=addr,
        estimand_id=spec.estimand_id,
        identification_status=report.status,
        reaction_level=spec.reaction_level,
        refused=False,
        adjustment_set=report.adjustment_set,
        assumptions=report.assumptions,
        distribution=dist,
        label="upper_bound_on_own_move" if spec.reaction_level == "L0" else None,
    )
