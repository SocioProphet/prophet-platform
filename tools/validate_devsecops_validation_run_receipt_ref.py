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
EXTERNAL_RECEIPT_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "sociosphere-svf-validation-receipt.valid.json",
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
SOCIOSPHERE_REQUIRED_RECEIPT_FIELDS = {
    "schema_version",
    "receipt_id",
    "run_ref",
    "run_digest",
    "repo",
    "profile_ref",
    "plan_ref",
    "plan_digest",
    "policy_ref",
    "policy_digest",
    "input_digests",
    "output_digests",
    "certified_claims",
    "non_certified_claims",
    "verification",
    "issued_at",
    "non_claims",
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


def digest_record_valid(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and record.get("algorithm") == "sha256"
        and isinstance(record.get("digest"), str)
        and len(record["digest"]) == 64
    )


def named_digest_list_valid(items: Any) -> bool:
    return (
        isinstance(items, list)
        and bool(items)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("path"), str)
            and digest_record_valid(item)
            for item in items
        )
    )


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


def sociosphere_receipt_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    missing = sorted(SOCIOSPHERE_REQUIRED_RECEIPT_FIELDS - set(data))
    problems.extend(f"sociosphere receipt missing required field: {field}" for field in missing)

    if data.get("schema_version") != "1.0":
        problems.append("sociosphere receipt schema_version must be 1.0")
    if not str(data.get("receipt_id", "")).startswith("svf:receipt:"):
        problems.append("sociosphere receipt_id must start with svf:receipt:")
    if not str(data.get("run_ref", "")).startswith("svf:run:"):
        problems.append("sociosphere run_ref must start with svf:run:")
    if data.get("receipt_id") == data.get("run_ref"):
        problems.append("sociosphere receipt_id and run_ref must be distinct")
    if data.get("repo") != "SocioProphet/sociosphere":
        problems.append("sociosphere receipt fixture must identify SocioProphet/sociosphere")
    if data.get("profile_ref") != "svf:profile:sociosphere.dogfood":
        problems.append("sociosphere receipt fixture must use dogfood profile")
    if data.get("plan_ref") != "svf:plan:sociosphere.registry-dogfood":
        problems.append("sociosphere receipt fixture must use registry dogfood plan")
    if data.get("policy_ref") != "svf:policy:sociosphere.local-readonly":
        problems.append("sociosphere receipt fixture must use local-readonly policy")

    for field in ("run_digest", "plan_digest", "policy_digest"):
        if not digest_record_valid(data.get(field)):
            problems.append(f"sociosphere {field} must be a sha256 digest record")
    if not named_digest_list_valid(data.get("input_digests")):
        problems.append("sociosphere input_digests must be a non-empty named digest list")
    if not named_digest_list_valid(data.get("output_digests")):
        problems.append("sociosphere output_digests must be a non-empty named digest list")

    verification = data.get("verification", {})
    if not isinstance(verification, dict) or verification.get("status") != "verified":
        problems.append("sociosphere receipt fixture must be verified")
    if verification.get("verifier") != "sociosphere.svf_runner.local":
        problems.append("sociosphere receipt verifier must be sociosphere.svf_runner.local")

    certified = set(data.get("certified_claims", []))
    unsupported = sorted(certified - SUPPORTED_CERTIFIED_CLAIMS)
    if unsupported:
        problems.append(f"sociosphere receipt has unsupported certified claims: {unsupported}")
    required_certified = {"schema_conformant", "non_production_only", "receipt_integrity_verified"}
    missing_certified = sorted(required_certified - certified)
    if missing_certified:
        problems.append(f"sociosphere receipt missing certified claims: {missing_certified}")

    non_certified = set(data.get("non_certified_claims", []))
    missing_non_claims = sorted(REQUIRED_NON_CERTIFIED_CLAIMS - non_certified)
    if missing_non_claims:
        problems.append(f"sociosphere receipt missing required non-claims: {missing_non_claims}")

    return problems


def cross_fixture_problems(adapter: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    projection = adapter.get("workroom_projection", {})
    source_refs = projection.get("source_refs", {}) if isinstance(projection, dict) else {}

    if adapter.get("authority_boundary", {}).get("receipt_authority") != "sociosphere_svf":
        problems.append("adapter receipt_authority must be sociosphere_svf for Sociosphere receipt ingestion")
    if adapter.get("authority_boundary", {}).get("execution_authority") != "sociosphere_svf":
        problems.append("adapter execution_authority must be sociosphere_svf for Sociosphere receipt ingestion")
    if adapter.get("receipt_ref") != receipt.get("receipt_id"):
        problems.append("adapter receipt_ref must equal Sociosphere receipt_id")
    if adapter.get("run_ref") != receipt.get("run_ref"):
        problems.append("adapter run_ref must equal Sociosphere run_ref")
    if adapter.get("plan_ref") != receipt.get("plan_ref"):
        problems.append("adapter plan_ref must equal Sociosphere plan_ref")
    if adapter.get("policy_ref") != receipt.get("policy_ref"):
        problems.append("adapter policy_ref must equal Sociosphere policy_ref")
    if source_refs.get("validation_run_ref") != receipt.get("run_ref"):
        problems.append("adapter source_refs.validation_run_ref must equal Sociosphere run_ref")
    if projection.get("runtime_parity_level") != "synthetic_observed":
        problems.append("Sociosphere external receipt fixture must project only synthetic_observed in Workroom v0.1")
    return problems


def main() -> int:
    schema = load(SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    adapter_fixtures = [load(path) for path in VALID_FIXTURES]
    receipt_fixtures = [load(path) for path in EXTERNAL_RECEIPT_FIXTURES]

    for path, data in zip(VALID_FIXTURES, adapter_fixtures):
        schema_errors = schema_problems(schema, data)
        semantic_errors = semantic_problems(data)
        problems = schema_errors + semantic_errors
        failed = failed or bool(problems)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": schema_errors,
            "semantic": semantic_errors,
        }

    for path, data in zip(EXTERNAL_RECEIPT_FIXTURES, receipt_fixtures):
        semantic_errors = sociosphere_receipt_problems(data)
        failed = failed or bool(semantic_errors)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid_external_sociosphere_receipt",
            "semantic": semantic_errors,
        }

    if adapter_fixtures and receipt_fixtures:
        cross_errors = cross_fixture_problems(adapter_fixtures[0], receipt_fixtures[0])
        failed = failed or bool(cross_errors)
        results["cross_fixture:sociosphere_receipt_adapter"] = {
            "expected": "adapter_matches_external_receipt",
            "semantic": cross_errors,
        }

    report = {
        "validator": "prophet-platform.devsecops-validation-run-receipt-ref.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks Workroom references to external validation run receipts.",
            "Validator checks Sociosphere-shaped receipt fixture semantics.",
            "Validator does not recompute Sociosphere artifact digests.",
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
