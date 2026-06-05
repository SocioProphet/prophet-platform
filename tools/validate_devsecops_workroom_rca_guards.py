#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_devsecops_workroom as base  # noqa: E402

FIXTURES = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.rca-claim-missing-evidence-ref.invalid.json": [
        "references missing evidence ref",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.confirmed-claim-without-counterevidence.invalid.json": [
        "confirmed causal claims require counterevidence handling",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.remediation-disconnected-from-causal-evidence.invalid.json": [
        "remediation evidence must overlap causal claim evidence",
    ],
}
CAUSAL_STATUSES = {"supported_causal_claim", "confirmed_causal_claim"}
HIGH_RISK_PLAN_CLASSES = {"high", "critical"}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def rca_linkage_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    claims = data.get("rca_claims", [])
    plans = data.get("remediation_plans", [])
    causal_evidence: set[str] = set()
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            continue
        if claim.get("claim_status") in CAUSAL_STATUSES:
            causal_evidence.update(str(ref) for ref in claim.get("evidence_refs", []) if isinstance(ref, str))
    for plan in plans if isinstance(plans, list) else []:
        if not isinstance(plan, dict):
            continue
        if plan.get("risk_class") not in HIGH_RISK_PLAN_CLASSES:
            continue
        plan_evidence = {str(ref) for ref in plan.get("evidence_refs", []) if isinstance(ref, str)}
        if plan_evidence and causal_evidence and not plan_evidence.intersection(causal_evidence):
            problems.append(f"{plan.get('plan_id')}: remediation evidence must overlap causal claim evidence")
    return problems


def expect(path: Path, problems: list[str], expected_substrings: list[str]) -> list[str]:
    failures: list[str] = []
    if not problems:
        failures.append(f"{path}: expected invalid fixture to fail, but it passed")
    for expected in expected_substrings:
        if not any(expected in problem for problem in problems):
            failures.append(f"{path}: expected problem containing {expected!r}")
    return failures


def main() -> int:
    schema = base.load(base.SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}
    for path, expected in FIXTURES.items():
        data = load(path)
        schema_errors = base.schema_problems(schema, data)
        semantic_errors = base.semantic_problems(data)
        linkage_errors = rca_linkage_problems(data)
        problems = schema_errors + semantic_errors + linkage_errors
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid",
            "expected_problem_substrings": expected,
            "expectation_failures": failures,
            "schema": schema_errors,
            "semantic": semantic_errors,
            "rca_linkage": linkage_errors,
        }
    report = {
        "validator": "prophet-platform.devsecops-workroom-rca-guards.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks fixture-scoped RCA evidence linkage.",
            "Validator performs no runtime operations.",
            "Validator makes no root-cause finding."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops workroom RCA guards")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
