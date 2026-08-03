"""validate-submission — the single MLPerf-parity submission-validity check.

WIRES the gates that already exist across the estate into ONE pass/fail verdict
per division, driven by the spec-as-code in ``schemas/eval/division-rules.json``:

  * governance_gate      — Stage-0 fail-closed floor (isota_tournament.py)
  * provider_neutrality  — scored by our runner, no provider term in scoring
  * no_laundering        — every headline fact is reproduced-by-us, disjoint
                           from cited provider numbers (metric-fact schema)
  * clean_eval_certificate — a pre-run contamination/clean-eval cert, status 'clean'
  * repro_ledger_entry   — env + methodology + seed pinning (repro-ledger schema)
  * fixed_task_manifest  — canonical benchmark contract run unchanged (CLOSED only)
  * minimum_trials_met   — trial_count >= contract minimum

A submission is VALID for its division iff every REQUIRED gate for that
division passes. Nothing here re-implements a gate's policy; it reads the
evidence each gate already defines and composes one verdict.

Usage:
    python tools/validate_submission.py <submission.json> [--min-trials N]
    # exit 0 = VALID, exit 1 = REJECTED, exit 2 = malformed input
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "eval"
DIVISION_RULES_PATH = SCHEMA_DIR / "division-rules.json"

# Governance floor keys — identical to isota_tournament.py Stage 0 (single source of truth for the flags).
GOVERNANCE_KEYS = ("api", "rate", "auth", "cost", "observability")
# Trust classes that count as reproduced-by-us (not a cited provider number).
INTERNAL_TRUST = frozenset({"internal_reproduced", "internal_live", "independent_harness"})


def load_division_rules() -> dict[str, Any]:
    return json.loads(DIVISION_RULES_PATH.read_text())


@dataclass
class GateResult:
    gate: str
    passed: bool
    reason: str


@dataclass
class SubmissionVerdict:
    submission_id: str
    division: str
    valid: bool
    required_gates: list[str]
    results: list[GateResult] = field(default_factory=list)

    def failed_gates(self) -> list[str]:
        return [r.gate for r in self.results if r.gate in self.required_gates and not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "division": self.division,
            "valid": self.valid,
            "required_gates": self.required_gates,
            "gate_results": [{"gate": r.gate, "passed": r.passed, "reason": r.reason} for r in self.results],
            "failed_required_gates": self.failed_gates(),
        }


# ── individual gate checks (each reads the evidence the gate already defines) ──
def _gate_governance(sub: dict) -> GateResult:
    gov = sub.get("governance") or {}
    missing = [k for k in GOVERNANCE_KEYS if gov.get(k) is not True]
    ok = not missing
    return GateResult("governance_gate", ok,
                      "all Stage-0 floor flags provisioned" if ok else f"governance floor not met: missing {missing}")


def _gate_provider_neutrality(sub: dict) -> GateResult:
    pn = sub.get("provider_neutrality") or {}
    scored_by = pn.get("scored_by")
    terms = pn.get("provider_terms_in_scoring")
    ok = scored_by in ("internal_runner", "independent_harness") and terms is False
    if scored_by == "provider_reported":
        reason = "scored by provider-reported numbers (not provider-neutral)"
    elif terms is not False:
        reason = "provider terms present in scoring"
    else:
        reason = "scored by neutral runner, no provider term in scoring"
    return GateResult("provider_neutrality", ok, reason)


def _gate_no_laundering(sub: dict) -> GateResult:
    facts = sub.get("metric_facts") or []
    headline = [f for f in facts if f.get("is_headline")]
    if not headline:
        return GateResult("no_laundering", False, "no headline metric fact to stand on")
    laundered = [
        f.get("metric_definition_id", "?")
        for f in headline
        if not (f.get("reproduced_by_us") is True and f.get("source_trust_class") in INTERNAL_TRUST)
    ]
    ok = not laundered
    return GateResult("no_laundering", ok,
                      "all headline facts reproduced-by-us, disjoint from cited" if ok
                      else f"laundered headline facts (cited/not-reproduced): {laundered}")


def _gate_clean_eval(sub: dict) -> GateResult:
    cert = sub.get("clean_eval_certificate")
    if not cert:
        return GateResult("clean_eval_certificate", False, "no clean-eval/contamination certificate")
    ok = cert.get("status") == "clean"
    return GateResult("clean_eval_certificate", ok,
                      "clean-eval certificate present and clean" if ok
                      else f"clean-eval certificate status={cert.get('status')!r} (must be 'clean')")


def _gate_repro_ledger(sub: dict) -> GateResult:
    entry = sub.get("repro_ledger_entry")
    if not entry:
        return GateResult("repro_ledger_entry", False, "no repro-ledger entry")
    required = ("run_id", "environment_hash", "methodology_snapshot_hash")
    missing = [k for k in required if not entry.get(k)]
    ok = not missing
    return GateResult("repro_ledger_entry", ok,
                      "repro-ledger entry pins env + methodology" if ok
                      else f"repro-ledger entry incomplete: missing {missing}")


def _gate_fixed_manifest(sub: dict) -> GateResult:
    manifest = sub.get("task_manifest") or {}
    ok = manifest.get("unchanged") is True
    return GateResult("fixed_task_manifest", ok,
                      "canonical task manifest run unchanged" if ok
                      else "task manifest deviated (not allowed in CLOSED)")


def _gate_minimum_trials(sub: dict, min_trials: int | None) -> GateResult:
    floor = min_trials if min_trials is not None else sub.get("minimum_trial_count")
    if not floor:
        return GateResult("minimum_trials_met", False, "no minimum_trial_count declared")
    headline = [f for f in (sub.get("metric_facts") or []) if f.get("is_headline")]
    worst = min((f.get("trial_count", 0) for f in headline), default=0)
    ok = worst >= floor
    return GateResult("minimum_trials_met", ok,
                      f"trial_count {worst} >= {floor}" if ok else f"trial_count {worst} < required {floor}")


GATE_FUNCS = {
    "governance_gate": _gate_governance,
    "provider_neutrality": _gate_provider_neutrality,
    "no_laundering": _gate_no_laundering,
    "clean_eval_certificate": _gate_clean_eval,
    "repro_ledger_entry": _gate_repro_ledger,
    "fixed_task_manifest": _gate_fixed_manifest,
}


def validate_submission(sub: dict, rules: dict | None = None, min_trials: int | None = None) -> SubmissionVerdict:
    """Run every gate; a submission is VALID iff all REQUIRED gates for its division pass."""
    rules = rules or load_division_rules()
    division = sub.get("division")
    div_spec = (rules.get("divisions") or {}).get(division)
    if div_spec is None:
        raise ValueError(f"unknown division {division!r} (expected one of {list((rules.get('divisions') or {}))})")
    required = list(div_spec.get("required_gates", []))

    results: list[GateResult] = []
    for name, fn in GATE_FUNCS.items():
        results.append(fn(sub))
    results.append(_gate_minimum_trials(sub, min_trials))

    valid = all(r.passed for r in results if r.gate in required)
    return SubmissionVerdict(
        submission_id=sub.get("submission_id", "?"), division=division,
        valid=valid, required_gates=required, results=results,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="validate a benchmark submission against the division rules")
    ap.add_argument("submission", type=Path, help="path to a submission JSON")
    ap.add_argument("--min-trials", type=int, default=None, help="override the minimum trial floor")
    args = ap.parse_args(argv)
    try:
        sub = json.loads(args.submission.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"malformed submission: {exc}", file=sys.stderr)
        return 2
    try:
        verdict = validate_submission(sub, min_trials=args.min_trials)
    except ValueError as exc:
        print(f"invalid submission: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(verdict.to_dict(), indent=2))
    status = "VALID" if verdict.valid else "REJECTED"
    print(f"\n{status}: {verdict.submission_id} [{verdict.division}]"
          + ("" if verdict.valid else f" — failed required gates: {verdict.failed_gates()}"), file=sys.stderr)
    return 0 if verdict.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
