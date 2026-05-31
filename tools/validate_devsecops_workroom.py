#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.pre-merge-validation-failure.valid.json",
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json",
]

CLAIM_STATUSES = {
    "observation",
    "hypothesis",
    "supported_causal_claim",
    "confirmed_causal_claim",
    "falsified_claim",
    "unknown",
}
CAUSAL_STATUSES = {"supported_causal_claim", "confirmed_causal_claim"}
HIGH_RISK_PLAN_CLASSES = {"high", "critical"}
MUTATION_ACTION_CLASSES = {
    "diagnostic_mutation",
    "reversible_mitigation",
    "irreversible_mutation",
    "credential_sensitive",
    "data_sensitive",
    "customer_visible",
    "destructive",
    "privileged_identity",
    "network_exposure",
    "production_change",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def ref_set(items: list[dict[str, Any]], key: str) -> set[str]:
    return {str(item.get(key)) for item in items if isinstance(item, dict)}


def validate_record(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    if data.get("schema_version") != "0.1.0":
        problems.append("schema_version must be 0.1.0")
    if not str(data.get("workroom_id", "")).startswith("workroom:devsecops:"):
        problems.append("workroom_id must start with workroom:devsecops:")

    lane = data.get("lane")
    parity = data.get("runtime_parity_level")
    bde = data.get("behavioral_divergence_event", {})
    evidence_packets = data.get("evidence_packets", [])
    claims = data.get("rca_claims", [])
    action_grants = data.get("action_grants", [])
    remediation_plans = data.get("remediation_plans", [])
    regression_fixtures = data.get("regression_fixtures", [])

    if lane not in {"pre_merge_validation", "post_merge_incident"}:
        problems.append("lane must be pre_merge_validation or post_merge_incident")
    if parity not in {"contract_only", "synthetic_observed", "runtime_observed"}:
        problems.append("runtime_parity_level is invalid")

    if not isinstance(bde, dict):
        problems.append("behavioral_divergence_event must be an object")
        bde = {}
    if bde.get("source_lane") != lane:
        problems.append("behavioral_divergence_event.source_lane must match workroom lane")

    evidence_refs = ref_set(evidence_packets, "evidence_ref") if isinstance(evidence_packets, list) else set()
    claim_ids = ref_set(claims, "claim_id") if isinstance(claims, list) else set()
    grant_ids = ref_set(action_grants, "grant_id") if isinstance(action_grants, list) else set()

    if not evidence_refs:
        problems.append("at least one evidence packet is required")
    if not claim_ids:
        problems.append("at least one RCA claim is required")

    for ref in bde.get("evidence_refs", []) if isinstance(bde.get("evidence_refs"), list) else []:
        if ref not in evidence_refs:
            problems.append(f"BDE references missing evidence ref: {ref}")
    for ref in bde.get("claim_refs", []) if isinstance(bde.get("claim_refs"), list) else []:
        if ref not in claim_ids:
            problems.append(f"BDE references missing claim ref: {ref}")

    for claim in claims if isinstance(claims, list) else []:
        claim_id = claim.get("claim_id")
        status = claim.get("claim_status")
        refs = claim.get("evidence_refs", [])
        counterrefs = claim.get("counterevidence_refs", [])
        confidence = claim.get("confidence")

        if status not in CLAIM_STATUSES:
            problems.append(f"{claim_id}: invalid claim_status")
        if status in CAUSAL_STATUSES and not refs:
            problems.append(f"{claim_id}: causal claims require evidence refs")
        if status == "confirmed_causal_claim" and not counterrefs:
            problems.append(f"{claim_id}: confirmed causal claims require counterevidence handling")
        if status == "unknown" and confidence != "none":
            problems.append(f"{claim_id}: unknown claims must have confidence none")
        for ref in refs:
            if ref not in evidence_refs:
                problems.append(f"{claim_id}: references missing evidence ref {ref}")
        for ref in counterrefs:
            if ref not in evidence_refs:
                problems.append(f"{claim_id}: references missing counterevidence ref {ref}")

    for grant in action_grants if isinstance(action_grants, list) else []:
        grant_id = grant.get("grant_id")
        action_class = grant.get("action_class")
        status = grant.get("status")
        approval_required = grant.get("approval_required")
        if action_class in MUTATION_ACTION_CLASSES and status == "allowed" and not approval_required:
            problems.append(f"{grant_id}: mutation-class actions cannot be allowed without approval requirement")
        if action_class == "read_only" and approval_required:
            problems.append(f"{grant_id}: read_only grants should not require approval in v0.1 fixtures")

    for plan in remediation_plans if isinstance(remediation_plans, list) else []:
        plan_id = plan.get("plan_id")
        risk_class = plan.get("risk_class")
        required_grants = plan.get("required_action_grant_refs", [])
        if risk_class in HIGH_RISK_PLAN_CLASSES and not required_grants:
            problems.append(f"{plan_id}: high/critical remediation requires action grant refs")
        for ref in required_grants:
            if ref not in grant_ids:
                problems.append(f"{plan_id}: references missing action grant {ref}")

    if lane == "pre_merge_validation":
        if bde.get("event_type") == "production_incident":
            problems.append("pre_merge_validation lane must not use production_incident event_type")
    if lane == "post_merge_incident":
        if bde.get("event_type") not in {"production_incident", "post_deploy_degradation", "customer_impact_event"}:
            problems.append("post_merge_incident lane must use incident-class event type")

    if parity == "runtime_observed":
        # v0.1 fixtures must stay below runtime_observed until live parity gates have evidence.
        problems.append("v0.1 fixture must not claim runtime_observed")

    if not regression_fixtures:
        problems.append("at least one regression fixture candidate is required")

    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list) or not non_claims:
        problems.append("non_claims must be non-empty")

    return problems


def main() -> int:
    failed = False
    results: dict[str, list[str]] = {}

    for path in FIXTURES:
        problems = validate_record(load(path))
        results[str(path.relative_to(ROOT))] = problems
        failed = failed or bool(problems)

    report = {
        "validator": "prophet-platform.devsecops-workroom.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks workroom fixture semantics only.",
            "Validator does not execute live sandbox infrastructure.",
            "Validator does not certify Signadot-style runtime parity.",
            "Validator does not authorize production remediation."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops workroom fixtures")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
