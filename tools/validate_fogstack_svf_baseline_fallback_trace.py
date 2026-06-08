#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts" / "runtime" / "baseline-fallback-observation" / "fogstack-svf-baseline-fallback-trace.v0.1.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def main() -> int:
    problems: list[str] = []
    data = load(FIXTURE)

    if data.get("record_type") != "FogStackSVFBaselineFallbackTraceObservation":
        problems.append("record_type mismatch")
    if data.get("observation_scope") != "nonprod_fixture_observation":
        problems.append("observation_scope must be nonprod_fixture_observation")
    if not str(data.get("workroom_ref", "")).startswith("workroom:devsecops:runtime-parity:"):
        problems.append("workroom_ref shape mismatch")

    change = data.get("change_set", {})
    changed_refs = set(change.get("changed_service_refs", []))
    unchanged_refs = set(change.get("unchanged_service_refs", []))
    if not changed_refs:
        problems.append("changed_service_refs must be non-empty")
    if not unchanged_refs:
        problems.append("unchanged_service_refs must be non-empty")
    if changed_refs & unchanged_refs:
        problems.append("changed and unchanged service refs must not overlap")

    deploy = data.get("changed_service_deploy", {})
    if deploy.get("deploy_state") != "observed_changed_service_only":
        problems.append("changed service deploy must be observed_changed_service_only")
    if set(deploy.get("changed_service_refs", [])) != changed_refs:
        problems.append("deploy changed_service_refs must match change_set")
    if set(deploy.get("baseline_service_refs", [])) != unchanged_refs:
        problems.append("deploy baseline_service_refs must match unchanged services")
    if not deploy.get("deployment_trace_ref"):
        problems.append("deployment_trace_ref is required")

    routing = data.get("routing_trace", {})
    if routing.get("routing_key_propagation_state") != "observed_header_propagated":
        problems.append("routing key propagation must be observed_header_propagated")
    if routing.get("baseline_fallback_state") != "observed_traffic_trace":
        problems.append("baseline fallback state must be observed_traffic_trace")
    if routing.get("trace_result") != "passed":
        problems.append("routing trace_result must be passed")
    total = routing.get("request_count")
    changed = routing.get("changed_service_request_count")
    baseline = routing.get("baseline_fallback_request_count")
    if not all(isinstance(x, int) and x >= 0 for x in [total, changed, baseline]):
        problems.append("routing request counts must be non-negative integers")
    elif total != changed + baseline:
        problems.append("request_count must equal changed_service_request_count + baseline_fallback_request_count")
    if not routing.get("request_trace_ref"):
        problems.append("request_trace_ref is required")

    job = data.get("validation_job", {})
    if job.get("job_state") != "observed_passed":
        problems.append("validation job must be observed_passed")
    if not job.get("receipt_ref"):
        problems.append("validation job receipt_ref is required")
    if not job.get("artifact_refs"):
        problems.append("validation job artifact_refs are required")

    isolation = data.get("isolation_observations", {})
    if isolation.get("http_grpc_route_isolation") != "observed_fixture_trace_only":
        problems.append("http_grpc_route_isolation must be observed_fixture_trace_only")
    for key in ["async_queue_topic_isolation", "stateful_resource_isolation", "network_policy_enforcement", "leak_check"]:
        if isolation.get(key) != "not_observed":
            problems.append(f"{key} must remain not_observed")

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
        "changed_service_only_deploy_trace_observed",
        "baseline_fallback_traffic_trace_observed",
        "routing_key_header_propagation_observed",
        "validation_job_observed_passed",
        "receipt_ref_present",
    }
    if missing := sorted(required_certified - certified):
        problems.append(f"missing certified claims: {missing}")

    non_certified = set(data.get("non_certified_claims", []))
    required_non_certified = {
        "signadot_vendor_parity",
        "production_readiness",
        "live_cluster_execution",
        "network_isolation_enforced",
        "service_mesh_runtime_parity",
        "async_queue_topic_isolation_observed",
        "stateful_resource_isolation_observed",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized",
    }
    if missing := sorted(required_non_certified - non_certified):
        problems.append(f"missing non-certified claims: {missing}")
    if overlap := sorted(certified & non_certified):
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
        "validator": "prophet-platform.fogstack-svf-baseline-fallback-trace.validator.v1",
        "passed": not problems,
        "problems": problems,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks a non-production baseline fallback trace fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": FogStack SVF baseline fallback trace")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
