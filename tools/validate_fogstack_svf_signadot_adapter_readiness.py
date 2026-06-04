#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "svf" / "fogstack-svf-signadot-adapter-readiness.example.json"

REQUIRED_NON_CERTIFIED = {
    "signadot_vendor_parity",
    "production_readiness",
    "live_cluster_execution",
    "live_infrastructure_safety",
    "network_isolation_enforced",
    "service_mesh_runtime_parity",
    "gitops_controller_reconciliation",
    "external_kms_hsm_signing",
}

REQUIRED_BLOCKING_REASONS = {
    "vendor_runtime_not_observed",
    "live_cluster_execution_not_observed",
    "network_isolation_not_certified",
    "production_readiness_not_certified",
}

REQUIRED_NEGATIVE_CONTROLS = {
    "claim_signadot_vendor_parity_true",
    "claim_production_readiness_true",
    "missing_policy_decision_ref",
    "missing_agentplane_run_ref",
    "missing_teardown_or_expiry_evidence",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def valid_sha256_digest(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("algorithm") == "sha256"
        and isinstance(value.get("digest"), str)
        and len(value["digest"]) == 64
        and all(c in "0123456789abcdef" for c in value["digest"])
    )


def non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def main() -> int:
    data = load_json(FIXTURE)
    problems: list[str] = []

    if data.get("schema_version") != "0.1.0":
        problems.append("schema_version must be 0.1.0")
    if data.get("record_type") != "FogStackSVFAdapterReadiness":
        problems.append("record_type must be FogStackSVFAdapterReadiness")
    if data.get("backend_mode") != "signadot_pattern_import":
        problems.append("backend_mode must remain signadot_pattern_import until a real adapter exists")

    claim_boundary = data.get("claim_boundary", {})
    if not isinstance(claim_boundary, dict):
        problems.append("claim_boundary must be an object")
        claim_boundary = {}
    non_certified = set(claim_boundary.get("non_certified_claims", []))
    missing_non_certified = sorted(REQUIRED_NON_CERTIFIED - non_certified)
    if missing_non_certified:
        problems.append(f"missing required non_certified_claims: {missing_non_certified}")
    certified = set(claim_boundary.get("certified_claims", []))
    forbidden_certified = certified & REQUIRED_NON_CERTIFIED
    if forbidden_certified:
        problems.append(f"forbidden certified claims present: {sorted(forbidden_certified)}")

    change_set = data.get("change_set", {})
    if not isinstance(change_set, dict):
        problems.append("change_set must be an object")
        change_set = {}
    if not non_empty_str(change_set.get("repo")) or "/" not in str(change_set.get("repo", "")):
        problems.append("change_set.repo must be owner/repo")
    if not non_empty_str(change_set.get("ref")):
        problems.append("change_set.ref is required")
    if not isinstance(change_set.get("changed_paths"), list) or not change_set.get("changed_paths"):
        problems.append("change_set.changed_paths must be non-empty")
    if not valid_sha256_digest(change_set.get("change_digest")):
        problems.append("change_set.change_digest must be sha256 with a 64-char lowercase hex digest")
    actor = change_set.get("actor", {})
    if not isinstance(actor, dict) or not non_empty_str(actor.get("actor_id")):
        problems.append("change_set.actor.actor_id is required")

    sandbox = data.get("sandbox_lease", {})
    if not isinstance(sandbox, dict):
        problems.append("sandbox_lease must be an object")
        sandbox = {}
    for key in ("lease_ref", "lease_state", "baseline_environment_ref", "expires_at", "teardown_evidence_ref"):
        if not non_empty_str(sandbox.get(key)):
            problems.append(f"sandbox_lease.{key} is required")
    if sandbox.get("lease_state") == "live_observed":
        problems.append("example fixture must not claim live_observed lease_state")
    if not isinstance(sandbox.get("changed_service_set"), list) or not sandbox.get("changed_service_set"):
        problems.append("sandbox_lease.changed_service_set must be non-empty")

    routing = data.get("routing_context", {})
    if not isinstance(routing, dict):
        problems.append("routing_context must be an object")
        routing = {}
    if not valid_sha256_digest(routing.get("routing_key_hash")):
        problems.append("routing_context.routing_key_hash must be sha256 with a 64-char lowercase hex digest")
    if not non_empty_str(routing.get("context_propagation_profile")):
        problems.append("routing_context.context_propagation_profile is required")
    mesh_plan = routing.get("mesh_routing_plan", {})
    if not isinstance(mesh_plan, dict):
        problems.append("routing_context.mesh_routing_plan must be an object")
        mesh_plan = {}
    if mesh_plan.get("baseline_fallback") is not True:
        problems.append("mesh_routing_plan.baseline_fallback must be true for Signadot-style SVF")
    if not isinstance(mesh_plan.get("required_headers"), list) or not mesh_plan.get("required_headers"):
        problems.append("mesh_routing_plan.required_headers must be non-empty")
    if mesh_plan.get("routing_mode") == "live_request_routing_observed":
        problems.append("example fixture must not claim live_request_routing_observed")

    validation_plan = data.get("validation_plan", {})
    if not isinstance(validation_plan, dict):
        problems.append("validation_plan must be an object")
        validation_plan = {}
    if validation_plan.get("required_evidence_state") != "verified_receipt":
        problems.append("validation_plan.required_evidence_state must be verified_receipt")
    jobs = validation_plan.get("jobs", [])
    if not isinstance(jobs, list) or not jobs:
        problems.append("validation_plan.jobs must be non-empty")
    for idx, job in enumerate(jobs if isinstance(jobs, list) else []):
        if not isinstance(job, dict):
            problems.append(f"validation_plan.jobs[{idx}] must be an object")
            continue
        for key in ("job_ref", "command_ref", "timeout_seconds"):
            if key == "timeout_seconds":
                if not isinstance(job.get(key), int) or job.get(key) <= 0:
                    problems.append(f"validation_plan.jobs[{idx}].timeout_seconds must be a positive integer")
            elif not non_empty_str(job.get(key)):
                problems.append(f"validation_plan.jobs[{idx}].{key} is required")
        if not isinstance(job.get("required_artifacts"), list) or not job.get("required_artifacts"):
            problems.append(f"validation_plan.jobs[{idx}].required_artifacts must be non-empty")

    policy_execution = data.get("policy_and_execution", {})
    if not isinstance(policy_execution, dict):
        problems.append("policy_and_execution must be an object")
        policy_execution = {}
    for key in ("policy_decision_ref", "agentplane_run_ref", "gitops_reconciliation_ref", "rollback_proof_ref"):
        if not non_empty_str(policy_execution.get(key)):
            problems.append(f"policy_and_execution.{key} is required")
    if policy_execution.get("policy_decision") not in {"allow_nonprod_modeled", "deny", "require_review"}:
        problems.append("policy_and_execution.policy_decision must be allow_nonprod_modeled, deny, or require_review")

    readiness = data.get("adapter_readiness", {})
    if not isinstance(readiness, dict):
        problems.append("adapter_readiness must be an object")
        readiness = {}
    if readiness.get("status") != "not_vendor_certified":
        problems.append("adapter_readiness.status must be not_vendor_certified")
    if readiness.get("merge_readiness") != "blocked_for_vendor_parity_claims":
        problems.append("adapter_readiness.merge_readiness must be blocked_for_vendor_parity_claims")
    blocking = set(readiness.get("blocking_reason_codes", []))
    missing_blocking = sorted(REQUIRED_BLOCKING_REASONS - blocking)
    if missing_blocking:
        problems.append(f"adapter_readiness missing blocking_reason_codes: {missing_blocking}")

    negative_controls = data.get("negative_controls", [])
    if not isinstance(negative_controls, list):
        problems.append("negative_controls must be a list")
        negative_controls = []
    observed_negative = {item.get("mutation") for item in negative_controls if isinstance(item, dict)}
    missing_negative = sorted(REQUIRED_NEGATIVE_CONTROLS - observed_negative)
    if missing_negative:
        problems.append(f"missing negative controls: {missing_negative}")
    for item in negative_controls:
        if isinstance(item, dict) and item.get("expected_result") != "reject":
            problems.append(f"negative control must reject: {item.get('mutation')}")

    report = {
        "validator": "fogstack-svf-signadot-adapter-readiness.v0.1",
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Validator checks a contract fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not certify production readiness or vendor parity.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Fog Stack SVF Signadot adapter readiness")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
