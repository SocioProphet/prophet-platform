#!/usr/bin/env python3
"""
Validator for DevSecOps ActionGrant fixtures.

Rules:
  1. credential_sensitive action cannot be status=allowed directly.
  2. production_change must require human approval (approval_required=true).
  3. destructive must require human approval.
  4. expired or revoked grant cannot be the active authorization for a remediation plan.
  5. read_only should not require approval in v0.1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-action-grant-v0.1.schema.json"

VALID_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-grant.read-only-allowed.valid.json",
]
INVALID_FIXTURES: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-grant.credential-sensitive-allowed.invalid.json": [
        "credential_sensitive action cannot be status=allowed directly",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-grant.production-change-no-approval.invalid.json": [
        "production_change grant must require human approval",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-grant.expired-status.invalid.json": [
        "expired or revoked grant cannot authorize a remediation plan",
    ],
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def schema_problems(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    v = jsonschema.Draft7Validator(schema)
    return [e.message for e in sorted(v.iter_errors(data), key=lambda e: list(e.path))]


def semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    grant_id = data.get("grant_id", "<unknown>")
    action_class = data.get("action_class", "")
    status = data.get("status", "")
    approval_required = data.get("approval_required", False)
    remediation_plan_ref = data.get("remediation_plan_ref")

    # Rule 1: credential_sensitive cannot be allowed directly
    if action_class == "credential_sensitive" and status == "allowed":
        problems.append(
            f"{grant_id}: credential_sensitive action cannot be status=allowed directly; requires_human_approval or denied only"
        )

    # Rule 2: production_change must require approval
    if action_class == "production_change" and not approval_required:
        problems.append(
            f"{grant_id}: production_change grant must require human approval (approval_required must be true)"
        )

    # Rule 3: destructive must require approval
    if action_class == "destructive" and not approval_required:
        problems.append(
            f"{grant_id}: destructive grant must require human approval (approval_required must be true)"
        )

    # Rule 4: expired/revoked grant cannot authorize remediation
    if status in ("expired", "revoked") and remediation_plan_ref:
        problems.append(
            f"{grant_id}: expired or revoked grant cannot authorize a remediation plan (remediation_plan_ref must be absent)"
        )

    return problems


def expect(path: Path, problems: list[str], expected_substrings: list[str]) -> list[str]:
    failures: list[str] = []
    if not problems:
        failures.append(f"{path}: expected invalid fixture to fail, but it passed")
    for expected in expected_substrings:
        if not any(expected in p for p in problems):
            failures.append(f"{path}: expected problem containing {expected!r}")
    return failures


def main() -> int:
    schema = load(SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    for path in VALID_FIXTURES:
        data = load(path)
        s_errs = schema_problems(schema, data)
        sem_errs = semantic_problems(data)
        failed = failed or bool(s_errs or sem_errs)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": s_errs,
            "semantic": sem_errs,
        }

    for path, expected in INVALID_FIXTURES.items():
        data = load(path)
        s_errs = schema_problems(schema, data)
        sem_errs = semantic_problems(data)
        problems = s_errs + sem_errs
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid",
            "expected_problem_substrings": expected,
            "expectation_failures": failures,
            "schema": s_errs,
            "semantic": sem_errs,
        }

    report = {
        "validator": "prophet-platform.devsecops-action-grant.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks grant contract structure and policy invariants only.",
            "Validator does not issue, approve, or certify grants.",
            "Validator does not execute actions or authorize production changes.",
            "Prophet Platform validates grant references; AgentPlane holds execution authority."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops action grant")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
