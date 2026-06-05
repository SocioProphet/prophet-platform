#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts" / "runtime" / "nonprod-sandbox-observation" / "fogstack-svf-nonprod-sandbox-observed.v0.1.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def main() -> int:
    problems: list[str] = []
    data = load(FIXTURE)

    if data.get("record_type") != "FogStackSVFNonprodSandboxObservation":
        problems.append("record_type mismatch")
    if data.get("observation_scope") != "nonprod_fixture_observation":
        problems.append("observation_scope must be nonprod_fixture_observation")
    if not str(data.get("workroom_ref", "")).startswith("workroom:devsecops:runtime-parity:"):
        problems.append("workroom_ref shape mismatch")

    lease = data.get("sandbox_lease", {})
    if lease.get("lease_state") != "observed_created":
        problems.append("sandbox lease must be observed_created")
    if lease.get("teardown_state") not in {"observed_expired", "observed_teardown_complete"}:
        problems.append("teardown_state must be observed_expired or observed_teardown_complete")
    if not lease.get("teardown_evidence_ref"):
        problems.append("teardown_evidence_ref is required")
    if not isinstance(lease.get("ttl_seconds"), int) or lease.get("ttl_seconds", 0) <= 0:
        problems.append("ttl_seconds must be positive")

    routing = data.get("routing", {})
    if routing.get("route_observation_state") != "observed_header_propagated":
        problems.append("route_observation_state must be observed_header_propagated")
    if routing.get("baseline_fallback_state") != "observed_declared_not_traffic_proven":
        problems.append("baseline fallback must remain declared_not_traffic_proven")
    if not routing.get("routing_trace_ref"):
        problems.append("routing_trace_ref is required")

    job = data.get("validation_job", {})
    if job.get("job_state") != "observed_passed":
        problems.append("validation job must be observed_passed")
    if not job.get("receipt_ref"):
        problems.append("validation job receipt_ref is required")
    if not job.get("artifact_refs"):
        problems.append("validation job artifact_refs are required")

    isolation = data.get("isolation_observations", {})
    for key in ["async_queue_topic_isolation", "stateful_resource_isolation", "network_policy_enforcement", "leak_check"]:
        if isolation.get(key) != "not_observed":
            problems.append(f"{key} must remain not_observed in this first fixture")

    gitops = data.get("gitops_reconciliation", {})
    if gitops.get("state") != "not_observed":
        problems.append("gitops reconciliation must remain not_observed")

    policy = data.get("policy_boundary", {})
    for key in ["live_apply_authorized", "cluster_mutation_authorized", "production_environment", "secret_access_authorized"]:
        if policy.get(key) is not False:
            problems.append(f"policy_boundary.{key} must be false")
    if policy.get("human_approval_required_for_live_apply") is not True:
        problems.append("human approval must be required for live apply")

    certified = set(data.get("certified_claims", []))
    required_certified = {
        "nonprod_sandbox_lease_observed_created",
        "routing_key_metadata_observed",
        "validation_job_observed_passed",
        "teardown_or_expiry_observed",
        "receipt_ref_present",
    }
    missing = sorted(required_certified - certified)
    if missing:
        problems.append(f"missing certified claims: {missing}")

    non_certified = set(data.get("non_certified_claims", []))
    required_non_certified = {
        "signadot_vendor_parity",
        "production_readiness",
        "live_cluster_execution",
        "network_isolation_enforced",
        "service_mesh_runtime_parity",
        "baseline_fallback_traffic_proven",
        "async_queue_topic_isolation_observed",
        "stateful_resource_isolation_observed",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized",
    }
    missing_non = sorted(required_non_certified - non_certified)
    if missing_non:
        problems.append(f"missing non-certified claims: {missing_non}")
    overlap = sorted(certified & non_certified)
    if overlap:
        problems.append(f"claims cannot be both certified and non-certified: {overlap}")

    non_claim_text = "\n".join(str(item) for item in data.get("non_claims", [])).lower()
    for phrase in [
        "does not call signadot",
        "does not authorize live apply",
        "does not authorize cluster mutation",
        "does not certify production readiness",
        "does not certify full signadot-style feature parity",
    ]:
        if not all(word in non_claim_text for word in phrase.split()):
            problems.append(f"non_claims missing posture {phrase!r}")

    report = {
        "validator": "prophet-platform.fogstack-svf-nonprod-sandbox-observation.validator.v1",
        "passed": not problems,
        "problems": problems,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks a non-production sandbox observation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": FogStack SVF nonprod sandbox observation")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
