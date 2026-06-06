#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_devsecops_workroom as workroom  # noqa: E402

VALID_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json",
]
INVALID_FIXTURES = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.unbacked-regression-candidate.invalid.json": [
        "regression fixture derived_from must reference the behavioral divergence event or an RCA claim",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.validation-plan-unpromoted-fixture.invalid.json": [
        "promoted validation plan cannot reference candidate regression fixture",
    ],
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def promotion_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    bde = data.get("behavioral_divergence_event", {})
    event_id = bde.get("event_id") if isinstance(bde, dict) else None
    claim_ids = {
        str(claim.get("claim_id"))
        for claim in data.get("rca_claims", [])
        if isinstance(claim, dict) and claim.get("claim_id")
    }
    regression_fixtures = data.get("regression_fixtures", [])
    validation_plans = data.get("validation_plans", [])
    fixture_status_by_id: dict[str, str] = {}

    for fixture in regression_fixtures if isinstance(regression_fixtures, list) else []:
        if not isinstance(fixture, dict):
            continue
        fixture_id = str(fixture.get("fixture_id", ""))
        fixture_status = str(fixture.get("fixture_status", ""))
        fixture_status_by_id[fixture_id] = fixture_status
        derived_from = str(fixture.get("derived_from", ""))
        if derived_from != event_id and derived_from not in claim_ids:
            problems.append(
                f"{fixture_id}: regression fixture derived_from must reference the behavioral divergence event or an RCA claim"
            )

    for plan in validation_plans if isinstance(validation_plans, list) else []:
        if not isinstance(plan, dict):
            continue
        plan_id = str(plan.get("plan_id", ""))
        plan_status = str(plan.get("plan_status", ""))
        for ref in plan.get("regression_fixture_refs", []):
            status = fixture_status_by_id.get(str(ref))
            if status is None:
                problems.append(f"{plan_id}: validation plan references unknown regression fixture {ref}")
            elif plan_status == "promoted" and status != "promoted":
                problems.append(f"{plan_id}: promoted validation plan cannot reference candidate regression fixture {ref}")
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
    schema = workroom.load(workroom.SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    for path in VALID_FIXTURES:
        data = load(path)
        schema_errors = workroom.schema_problems(schema, data)
        semantic_errors = workroom.semantic_problems(data)
        promotion_errors = promotion_problems(data)
        failed = failed or bool(schema_errors or semantic_errors or promotion_errors)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": schema_errors,
            "semantic": semantic_errors,
            "promotion": promotion_errors,
        }

    for path, expected in INVALID_FIXTURES.items():
        data = load(path)
        schema_errors = workroom.schema_problems(schema, data)
        semantic_errors = workroom.semantic_problems(data)
        promotion_errors = promotion_problems(data)
        problems = schema_errors + semantic_errors + promotion_errors
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid",
            "expected_problem_substrings": expected,
            "expectation_failures": failures,
            "schema": schema_errors,
            "semantic": semantic_errors,
            "promotion": promotion_errors,
        }

    report = {
        "validator": "prophet-platform.devsecops-regression-promotion.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks fixture-scoped regression promotion linkage.",
            "Validator performs no runtime operations.",
            "Validator does not promote fixtures by itself."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops regression promotion")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
