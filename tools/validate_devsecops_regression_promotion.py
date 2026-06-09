#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_devsecops_workroom as workroom  # noqa: E402

PROMOTION_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-regression-promotion-v0.1.schema.json"

# Valid fixtures: must pass Workroom broad schema+semantic AND promotion rules.
WORKROOM_VALID_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json",
]

# Valid fixtures that use the dedicated regression promotion schema.
PROMOTION_VALID_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.closed-loop.valid.json",
]

# Invalid fixtures validated against the broad Workroom schema + promotion rules.
WORKROOM_INVALID_FIXTURES: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.unbacked-regression-candidate.invalid.json": [
        "regression fixture derived_from must reference the behavioral divergence event or an RCA claim",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.validation-plan-unpromoted-fixture.invalid.json": [
        "promoted validation plan cannot reference candidate regression fixture",
    ],
}

# Invalid fixtures validated against the dedicated promotion schema + promotion rules.
PROMOTION_INVALID_FIXTURES: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.rejected-fixture-active-plan.invalid.json": [
        "active validation plan cannot reference rejected regression fixture",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-regression-promotion.candidate-blocking-gate.invalid.json": [
        "candidate regression fixture cannot hold blocking_gate authority",
    ],
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def promotion_schema_problems(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    v = jsonschema.Draft7Validator(schema)
    return [e.message for e in sorted(v.iter_errors(data), key=lambda e: list(e.path))]


def promotion_problems(data: dict[str, Any]) -> list[str]:
    """
    Checks promotion state machine rules:
    1. regression_fixture.derived_from must reference BDE event_id or an RCA claim_id.
    2. promoted validation plan cannot reference non-promoted fixture.
    3. active validation plan cannot reference rejected fixture.
    4. active or promoted plan cannot reference deprecated fixture.
    5. candidate fixture cannot hold blocking_gate authority.
    6. superseded fixture must identify a successor.
    """
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

        # Rule 1: derived_from must reference BDE or RCA claim
        if derived_from != event_id and derived_from not in claim_ids:
            problems.append(
                f"{fixture_id}: regression fixture derived_from must reference the behavioral divergence event or an RCA claim"
            )

        # Rule 5: candidate fixture cannot hold blocking_gate authority
        if fixture_status == "candidate" and fixture.get("blocking_gate") is True:
            problems.append(
                f"{fixture_id}: candidate regression fixture cannot hold blocking_gate authority"
            )

        # Rule 6: superseded fixture must identify a successor
        if fixture_status == "superseded" and not fixture.get("successor_fixture_ref"):
            problems.append(
                f"{fixture_id}: superseded regression fixture must identify a successor via successor_fixture_ref"
            )

    for plan in validation_plans if isinstance(validation_plans, list) else []:
        if not isinstance(plan, dict):
            continue
        plan_id = str(plan.get("plan_id", ""))
        plan_status = str(plan.get("plan_status", ""))
        for ref in plan.get("regression_fixture_refs", []):
            status = fixture_status_by_id.get(str(ref))
            if status is None:
                problems.append(
                    f"{plan_id}: validation plan references unknown regression fixture {ref}"
                )
                continue

            # Rule 2: promoted plan cannot reference non-promoted fixture
            if plan_status == "promoted" and status not in ("promoted",):
                problems.append(
                    f"{plan_id}: promoted validation plan cannot reference candidate regression fixture {ref}"
                )

            # Rule 3: active plan cannot reference rejected fixture
            if plan_status == "active" and status == "rejected":
                problems.append(
                    f"{plan_id}: active validation plan cannot reference rejected regression fixture {ref}"
                )

            # Rule 4: active or promoted plan cannot reference deprecated fixture
            if plan_status in ("active", "promoted") and status == "deprecated":
                problems.append(
                    f"{plan_id}: {plan_status} validation plan cannot reference deprecated regression fixture {ref}"
                )

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
    workroom_schema = workroom.load(workroom.SCHEMA)
    promotion_schema = load(PROMOTION_SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    # ── Broad Workroom valid fixtures ────────────────────────────────────────
    for path in WORKROOM_VALID_FIXTURES:
        data = load(path)
        schema_errors = workroom.schema_problems(workroom_schema, data)
        semantic_errors = workroom.semantic_problems(data)
        promo_errors = promotion_problems(data)
        failed = failed or bool(schema_errors or semantic_errors or promo_errors)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": schema_errors,
            "semantic": semantic_errors,
            "promotion": promo_errors,
        }

    # ── Dedicated promotion schema valid fixtures ────────────────────────────
    for path in PROMOTION_VALID_FIXTURES:
        data = load(path)
        schema_errors = promotion_schema_problems(promotion_schema, data)
        promo_errors = promotion_problems(data)
        failed = failed or bool(schema_errors or promo_errors)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": schema_errors,
            "promotion": promo_errors,
        }

    # ── Broad Workroom invalid fixtures ─────────────────────────────────────
    for path, expected in WORKROOM_INVALID_FIXTURES.items():
        data = load(path)
        schema_errors = workroom.schema_problems(workroom_schema, data)
        semantic_errors = workroom.semantic_problems(data)
        promo_errors = promotion_problems(data)
        problems = schema_errors + semantic_errors + promo_errors
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid",
            "expected_problem_substrings": expected,
            "expectation_failures": failures,
            "schema": schema_errors,
            "semantic": semantic_errors,
            "promotion": promo_errors,
        }

    # ── Dedicated promotion schema invalid fixtures ──────────────────────────
    for path, expected in PROMOTION_INVALID_FIXTURES.items():
        data = load(path)
        schema_errors = promotion_schema_problems(promotion_schema, data)
        promo_errors = promotion_problems(data)
        problems = schema_errors + promo_errors
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid",
            "expected_problem_substrings": expected,
            "expectation_failures": failures,
            "schema": schema_errors,
            "promotion": promo_errors,
        }

    report = {
        "validator": "prophet-platform.devsecops-regression-promotion.validator.v2",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks fixture-scoped regression promotion linkage and state machine rules.",
            "Validator performs no runtime operations.",
            "Validator does not promote fixtures by itself.",
            "Validator does not authorize validation plan enforcement or PR gating."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops regression promotion")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
