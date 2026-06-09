#!/usr/bin/env python3
"""
Validator for DevSecOps AgentPlane execution handoff and execution receipt reference contracts.

Handoff rules:
  1. receipt_received status requires execution_receipt_ref.
  2. failed status requires failure_evidence_ref.
  3. denied status must not have execution_receipt_ref.
  4. submitted status requires agentplane_execution_request_ref.

Receipt reference rules:
  1. success status requires artifact_digest.
  2. failed status requires failure_evidence_ref.
  3. not_executed must not carry artifact_digest.
  4. partial status cannot close remediation (informational warning, not hard failure).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-action-execution-handoff-v0.1.schema.json"
RECEIPT_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-action-execution-receipt-ref-v0.1.schema.json"

HANDOFF_VALID = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-execution-handoff.approved.valid.json",
]
HANDOFF_INVALID: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-execution-handoff.submitted-no-receipt.invalid.json": [
        "receipt_received handoff requires execution_receipt_ref",
    ],
}

RECEIPT_VALID = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-execution-receipt-ref.success.valid.json",
]
RECEIPT_INVALID: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-action-execution-receipt-ref.not-executed-success.invalid.json": [
        "not_executed receipt must not carry artifact_digest",
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


def handoff_semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    hid = data.get("handoff_id", "<unknown>")
    status = data.get("status", "")

    if status == "receipt_received" and not data.get("execution_receipt_ref"):
        problems.append(f"{hid}: receipt_received handoff requires execution_receipt_ref")

    if status == "failed" and not data.get("failure_evidence_ref"):
        problems.append(f"{hid}: failed handoff requires failure_evidence_ref")

    if status == "denied" and data.get("execution_receipt_ref"):
        problems.append(f"{hid}: denied handoff must not have execution_receipt_ref")

    if status == "submitted" and not data.get("agentplane_execution_request_ref"):
        problems.append(f"{hid}: submitted handoff requires agentplane_execution_request_ref")

    return problems


def receipt_semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    rid = data.get("receipt_ref", "<unknown>")
    status = data.get("status", "")

    if status == "success" and not data.get("artifact_digest"):
        problems.append(f"{rid}: success receipt requires artifact_digest")

    if status == "failed" and not data.get("failure_evidence_ref"):
        problems.append(f"{rid}: failed receipt requires failure_evidence_ref")

    if status == "not_executed" and data.get("artifact_digest"):
        problems.append(f"{rid}: not_executed receipt must not carry artifact_digest")

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
    handoff_schema = load(HANDOFF_SCHEMA)
    receipt_schema = load(RECEIPT_SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    # ── handoff valid ────────────────────────────────────────────────────────
    for path in HANDOFF_VALID:
        data = load(path)
        s_errs = schema_problems(handoff_schema, data)
        sem_errs = handoff_semantic_problems(data)
        failed = failed or bool(s_errs or sem_errs)
        results[str(path.relative_to(ROOT))] = {"expected": "valid", "schema": s_errs, "semantic": sem_errs}

    # ── handoff invalid ──────────────────────────────────────────────────────
    for path, expected in HANDOFF_INVALID.items():
        data = load(path)
        s_errs = schema_problems(handoff_schema, data)
        sem_errs = handoff_semantic_problems(data)
        problems = s_errs + sem_errs
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid", "expected_problem_substrings": expected,
            "expectation_failures": failures, "schema": s_errs, "semantic": sem_errs,
        }

    # ── receipt valid ────────────────────────────────────────────────────────
    for path in RECEIPT_VALID:
        data = load(path)
        s_errs = schema_problems(receipt_schema, data)
        sem_errs = receipt_semantic_problems(data)
        failed = failed or bool(s_errs or sem_errs)
        results[str(path.relative_to(ROOT))] = {"expected": "valid", "schema": s_errs, "semantic": sem_errs}

    # ── receipt invalid ──────────────────────────────────────────────────────
    for path, expected in RECEIPT_INVALID.items():
        data = load(path)
        s_errs = schema_problems(receipt_schema, data)
        sem_errs = receipt_semantic_problems(data)
        problems = s_errs + sem_errs
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid", "expected_problem_substrings": expected,
            "expectation_failures": failures, "schema": s_errs, "semantic": sem_errs,
        }

    report = {
        "validator": "prophet-platform.devsecops-agentplane-handoff.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks handoff and receipt reference contract structure only.",
            "Prophet Platform proposes handoffs and validates receipt references.",
            "AgentPlane executes actions and issues execution receipts.",
            "Validator does not execute actions, issue receipts, or authorize production changes.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops agentplane handoff")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
