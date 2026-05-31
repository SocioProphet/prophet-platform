#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-validation-run-receipt-ref-v0.1.schema.json"
VALID_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-validation-run-receipt-ref.svf.valid.json",
]
SUPPORTED_CERTIFIED_CLAIMS = {
    "schema_conformant",
    "fixtures_validated",
    "tests_passed",
    "semantic_roundtrip_preserved",
    "policy_boundary_preserved",
    "non_production_only",
    "runtime_smoke_passed",
    "artifact_integrity_verified",
    "receipt_integrity_verified",
}
REQUIRED_NON_CERTIFIED_CLAIMS = {
    "production_readiness",
    "live_infrastructure_safety",
    "signadot_vendor_parity",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def schema_problems(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    problems: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        problems.append(f"schema:{path}: {error.message}")
    return problems


def semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    boundary = data.get("authority_boundary", {})
    verification = data.get("verification", {})
    projection = data.get("workroom_projection", {})
    source_refs = projection.get("source_refs", {}) if isinstance(projection, dict) else {}

    if boundary.get("workroom_authority") != "prophet_platform":
        problems.append("workroom authority must remain prophet_platform")
    if boundary.get("execution_authority") == "prophet_platform":
        problems.append("Prophet Platform must not be the execution authority")
    if boundary.get("receipt_authority") == "prophet_platform":
        problems.append("Prophet Platform must not be the receipt authority")

    if data.get("receipt_ref") == data.get("run_ref"):
        problems.append("receipt_ref and run_ref must remain distinct")
    if source_refs.get("validation_run_ref") != data.get("run_ref"):
        problems.append("workroom_projection.source_refs.validation_run_ref must equal run_ref")

    status = verification.get("status")
    if status != "verified":
        problems.append("validation run receipt references must be verified before Workroom ingestion")

    certified = set(data.get("certified_claims", []))
    unsupported = sorted(certified - SUPPORTED_CERTIFIED_CLAIMS)
    if unsupported:
        problems.append(f"certified_claims contains unsupported scopes: {unsupported}")

    non_certified = set(data.get("non_certified_claims", []))
    missing_non_claims = sorted(REQUIRED_NON_CERTIFIED_CLAIMS - non_certified)
    if missing_non_claims:
        problems.append(f"non_certified_claims missing required non-claims: {missing_non_claims}")

    parity = projection.get("runtime_parity_level") if isinstance(projection, dict) else None
    if parity == "runtime_observed" and "signadot_vendor_parity" in non_certified:
        problems.append("runtime_observed cannot be projected while Signadot vendor parity is non-certified")

    return problems


def main() -> int:
    schema = load(SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    for path in VALID_FIXTURES:
        data = load(path)
        schema_errors = schema_problems(schema, data)
        semantic_errors = semantic_problems(data)
        problems = schema_errors + semantic_errors
        failed = failed or bool(problems)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": schema_errors,
            "semantic": semantic_errors,
        }

    report = {
        "validator": "prophet-platform.devsecops-validation-run-receipt-ref.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks Workroom references to external validation run receipts.",
            "Validator does not execute validation runs.",
            "Validator does not issue Sociosphere or AgentPlane receipts.",
            "Validator does not certify production readiness or Signadot vendor parity.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops validation run receipt refs")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
