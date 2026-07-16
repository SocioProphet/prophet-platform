"""engine.py — the experiment loop.

For each perturbation in a suite: run the synthetic cohort with NO fault (baseline completion), then WITH the
fault (perturbed completion), scoring every run into the Assay verdict + the silent-failure. Aggregate into a
resilience rollup with the SLO delta and the fleet-relevant silent-failure rate.

Two axes per run, kept deliberately separate:
  correct — did it achieve the goal (grounded / exact answer). Drives goal_completion_rate (the SLO).
  safe    — did it avoid the invariant's BAD outcome (fabrication, or serving revoked content).
Verdict is safety-first: not-safe ⇒ bad, else correct ⇒ ok, else (abstained safely) ⇒ sad.
silent_failure = the bad outcome occurred AND the run did not flag it — the metric infra chaos cannot measure.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from .domain import (
    ExperimentRollup,
    ExperimentSuite,
    Fault,
    Perturbation,
    ResilienceReceipt,
    RunOutcome,
    Verdict,
)
from .oracles import inv_exact_string, inv_grounded, invariant_holds
from .targets import get_target


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(model: ResilienceReceipt) -> str:
    d = model.model_dump(mode="json")
    d.pop("receipt_hash", None)
    return "sha256:" + hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _is_correct(invariant: str, output: str, task: dict) -> bool:
    """Goal completion — the RIGHT answer. exactString suites demand an exact match; everything else is grounded."""
    return inv_exact_string(output, task) if invariant == "exactString" else inv_grounded(output, task)


def score_run(invariant: str, task: dict, run: RunOutcome) -> tuple[Verdict, bool, bool]:
    """Return (verdict, silent_failure, recovered) for one run under a fault."""
    safe = invariant_holds(invariant, run.output, task)
    correct = _is_correct(invariant, run.output, task)
    if not safe:
        verdict = Verdict.bad
    elif correct:
        verdict = Verdict.ok
    else:
        verdict = Verdict.sad
    silent_failure = (not safe) and (not run.flagged)
    recovered = correct and run.steps > 1
    return verdict, silent_failure, recovered


def _completion(target_name: str, tasks: list[dict], invariant: str, fault: Optional[Fault]) -> float:
    target = get_target(target_name)
    if not tasks:
        return 0.0
    hits = sum(1 for t in tasks if _is_correct(invariant, target(t, fault).output, t))
    return hits / len(tasks)


def run_perturbation(experiment_id: str, suite: ExperimentSuite, pert: Perturbation, tasks: list[dict]) -> list[ResilienceReceipt]:
    target = get_target(suite.target)
    receipts: list[ResilienceReceipt] = []
    for t in tasks:
        run = target(t, pert.fault)
        verdict, silent, recovered = score_run(pert.invariant, t, run)
        r = ResilienceReceipt(
            experiment_id=experiment_id,
            suite_id=suite.suite_id,
            perturbation_id=pert.perturbation_id,
            plane=pert.plane,
            fault=pert.fault,
            task_id=str(t.get("task_id", "task")),
            invariant=pert.invariant,
            verdict=verdict,
            recovered=recovered,
            recovery_steps=run.steps,
            silent_failure=silent,
            issued_at=_utc(),
        )
        r.receipt_hash = _hash(r)
        receipts.append(r)
    return receipts


def run_experiment(suite: ExperimentSuite, tasks: list[dict], experiment_id: Optional[str] = None) -> ExperimentRollup:
    if suite.cohort.sample_rate <= 0 or not suite.cohort.roles:
        raise ValueError("cohort with a positive sample_rate and at least one role is required (no blind blast radius)")
    exp_id = experiment_id or f"experiment:{suite.suite_id.split(':')[-1]}:{int(datetime.now(timezone.utc).timestamp())}"

    all_receipts: list[ResilienceReceipt] = []
    before_vals: list[float] = []
    after_vals: list[float] = []
    for pert in suite.perturbations:
        before_vals.append(_completion(suite.target, tasks, pert.invariant, None))
        after_vals.append(_completion(suite.target, tasks, pert.invariant, pert.fault))
        all_receipts.extend(run_perturbation(exp_id, suite, pert, tasks))

    n = len(all_receipts)
    completion_before = sum(before_vals) / len(before_vals) if before_vals else 0.0
    completion_after = sum(after_vals) / len(after_vals) if after_vals else 0.0
    silent_rate = sum(1 for r in all_receipts if r.silent_failure) / n if n else 0.0
    recovered_rate = sum(1 for r in all_receipts if r.recovered) / n if n else 0.0
    verdicts = {v.value: sum(1 for r in all_receipts if r.verdict == v) for v in Verdict}
    slo_held = completion_after >= suite.steady_state.floor
    passed = slo_held and silent_rate == 0.0

    return ExperimentRollup(
        experiment_id=exp_id,
        suite_id=suite.suite_id,
        n=n,
        completion_before=round(completion_before, 4),
        completion_after=round(completion_after, 4),
        steady_state_floor=suite.steady_state.floor,
        slo_held=slo_held,
        silent_failure_rate=round(silent_rate, 4),
        verdicts=verdicts,
        recovered_rate=round(recovered_rate, 4),
        passed=passed,
        issued_at=_utc(),
        receipts=all_receipts,
    )
