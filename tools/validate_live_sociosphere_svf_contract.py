#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "svf" / "live-sociosphere-validate-change-v0.1.example.json"
UPSTREAM_EXPORT_MANIFEST = "SocioProphet/sociosphere@7133223edd7784a36b15e3eee9065f17b49b5451:artifacts/svf/exports/latest/export-manifest.json"
ALLOWED_STATES = {
    "not_configured",
    "selected_only",
    "missing_evidence",
    "synthetic_observed",
    "runtime_observed",
    "verified_receipt",
    "failed_receipt",
    "stale_receipt",
}
BLOCKING_STATES = {"selected_only", "missing_evidence", "failed_receipt", "stale_receipt"}
REQUIRED_NON_CLAIMS = {
    "production_readiness",
    "live_infrastructure_safety",
    "signadot_vendor_parity",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def digest_record_valid(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and record.get("algorithm") == "sha256"
        and isinstance(record.get("digest"), str)
        and len(record["digest"]) == 64
    )


def main() -> int:
    data = load(FIXTURE)
    problems: list[str] = []

    planes = data.get("planes", {})
    request = data.get("request", {})
    invocation = data.get("sociosphere_invocation", {})
    receipt = data.get("receipt_input", {})
    projection = data.get("prophet_response_projection", {})
    evidence_summary = projection.get("evidence_summary", {}) if isinstance(projection, dict) else {}
    pr_readiness = projection.get("pr_readiness", {}) if isinstance(projection, dict) else {}
    negative_controls = data.get("negative_controls", [])

    if data.get("schema_version") != "0.1.0":
        problems.append("schema_version must be 0.1.0")
    if data.get("contract_id") != "svf:live-sociosphere-validate-change-contract:v0.1":
        problems.append("unexpected contract_id")
    if data.get("issue_ref") != "SocioProphet/prophet-platform#549":
        problems.append("contract must reference #549")

    expected_planes = {
        "authority_plane": "SocioProphet/ProCybernetica",
        "workspace_plane": "SocioProphet/sociosphere",
        "agent_invocation_plane": "SocioProphet/prophet-platform",
        "execution_authority": "sociosphere_svf",
        "receipt_authority": "sociosphere_svf",
        "consumer_authority": "prophet_platform",
    }
    for key, expected in expected_planes.items():
        if planes.get(key) != expected:
            problems.append(f"planes.{key} must be {expected}")

    if planes.get("execution_authority") == "prophet_platform":
        problems.append("Prophet Platform must not be execution authority")
    if planes.get("receipt_authority") == "prophet_platform":
        problems.append("Prophet Platform must not be receipt authority")

    if request.get("repo") != "SocioProphet/sociosphere":
        problems.append("request repo must target Sociosphere for this fixture")
    if not digest_record_valid(request.get("change_digest")):
        problems.append("request.change_digest must be a sha256 digest")
    if not isinstance(request.get("changed_paths"), list) or not request.get("changed_paths"):
        problems.append("request.changed_paths must be non-empty")

    if invocation.get("mode") != "exported_receipt_or_live_runner":
        problems.append("invocation mode must be exported_receipt_or_live_runner")
    if invocation.get("selection_source") != "sociosphere_svf_registry":
        problems.append("selection_source must be sociosphere_svf_registry")
    forbidden = set(invocation.get("forbidden_commands", []))
    for item in ("arbitrary_shell", "production_mutation", "vendor_signadot_adapter"):
        if item not in forbidden:
            problems.append(f"forbidden_commands must include {item}")
    if invocation.get("selected_plan_ref") != "svf:plan:sociosphere.registry-dogfood":
        problems.append("selected_plan_ref must be Sociosphere registry dogfood plan")
    if invocation.get("policy_ref") != "svf:policy:sociosphere.local-readonly":
        problems.append("policy_ref must preserve local-readonly policy")

    if receipt.get("source_kind") != "exported_sociosphere_receipt":
        problems.append("receipt_input.source_kind must be exported_sociosphere_receipt")
    if not str(receipt.get("receipt_ref", "")).startswith("svf:receipt:"):
        problems.append("receipt_ref must start with svf:receipt:")
    if not str(receipt.get("run_ref", "")).startswith("svf:run:"):
        problems.append("run_ref must start with svf:run:")
    if receipt.get("export_manifest_ref") != UPSTREAM_EXPORT_MANIFEST:
        problems.append("receipt_input.export_manifest_ref must point at merged Sociosphere export manifest")
    if receipt.get("verification_status") != "verified":
        problems.append("positive fixture receipt must be verified")
    if receipt.get("verified_by") != "sociosphere.svf_runner.local":
        problems.append("verified_by must be sociosphere.svf_runner.local")
    non_certified = set(receipt.get("non_certified_claims", []))
    missing_non_claims = sorted(REQUIRED_NON_CLAIMS - non_certified)
    if missing_non_claims:
        problems.append(f"receipt_input missing required non-certified claims: {missing_non_claims}")

    state = evidence_summary.get("validation_evidence_state")
    if state not in ALLOWED_STATES:
        problems.append(f"invalid validation_evidence_state: {state}")
    if state != "verified_receipt":
        problems.append("positive fixture must project verified_receipt")
    receipt_refs = evidence_summary.get("receipt_refs", [])
    if receipt.get("receipt_ref") not in receipt_refs:
        problems.append("projection receipt_refs must include receipt_input.receipt_ref")
    if pr_readiness.get("required_evidence_state") != "verified_receipt":
        problems.append("pr_readiness must require verified_receipt")
    if pr_readiness.get("observed_evidence_state") != "verified_receipt":
        problems.append("positive fixture observed evidence state must be verified_receipt")
    if pr_readiness.get("merge_allowed") is not True:
        problems.append("positive fixture may allow merge only with verified_receipt")
    if pr_readiness.get("blocking_reason_codes") != []:
        problems.append("positive verified receipt fixture must have no blocking_reason_codes")

    if not isinstance(negative_controls, list) or len(negative_controls) < 4:
        problems.append("negative_controls must include the four blocking states")
    seen_negative_states = {item.get("state") for item in negative_controls if isinstance(item, dict)}
    missing_negative = sorted(BLOCKING_STATES - seen_negative_states)
    if missing_negative:
        problems.append(f"negative_controls missing states: {missing_negative}")
    for item in negative_controls if isinstance(negative_controls, list) else []:
        if item.get("state") in BLOCKING_STATES and item.get("merge_allowed") is not False:
            problems.append(f"negative control {item.get('state')} must block merge")

    non_claims = data.get("non_claims", [])
    for phrase in (
        "does not execute Sociosphere SVF Actions",
        "does not issue, sign, or certify receipts",
        "does not authorize production remediation",
        "does not claim Signadot vendor parity",
        "Sociosphere export manifest merged in SocioProphet/sociosphere#456",
    ):
        if not any(phrase in item for item in non_claims):
            problems.append(f"non_claims must include phrase: {phrase}")

    report = {
        "validator": "prophet-platform.live-sociosphere-svf-contract.validator.v1",
        "passed": not problems,
        "problems": problems,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks the contract fixture only.",
            "Validator does not invoke Sociosphere.",
            "Validator does not execute SVF Actions.",
            "Validator does not issue or certify receipts.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": live Sociosphere SVF contract")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
