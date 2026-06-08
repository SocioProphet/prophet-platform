#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "artifacts" / "runtime" / "workroom-runtime-parity-bridge" / "fogstack-svf-signadot-readiness.bridge.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def resolve(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    problems: list[str] = []
    bridge = load(BRIDGE)
    ref = bridge.get("source_records", {}).get("baseline_fallback_trace_ref")
    if not isinstance(ref, str) or not ref:
        problems.append("missing source_records.baseline_fallback_trace_ref")
        baseline = {}
    elif not resolve(ref).exists():
        problems.append(f"baseline fallback trace ref missing: {ref}")
        baseline = {}
    else:
        baseline = load(resolve(ref))

    observed = bridge.get("observed_evidence", {})
    if baseline:
        routing = baseline.get("routing_trace", {})
        deploy = baseline.get("changed_service_deploy", {})
        if observed.get("baseline_fallback_traffic_state") != routing.get("baseline_fallback_state"):
            problems.append("bridge baseline_fallback_traffic_state must match fixture")
        if observed.get("changed_service_deploy_state") != deploy.get("deploy_state"):
            problems.append("bridge changed_service_deploy_state must match fixture")
        if observed.get("baseline_fallback_request_count") != routing.get("baseline_fallback_request_count"):
            problems.append("bridge baseline_fallback_request_count must match fixture")
        if observed.get("changed_service_request_count") != routing.get("changed_service_request_count"):
            problems.append("bridge changed_service_request_count must match fixture")
        if observed.get("routing_key_propagation_state") != routing.get("routing_key_propagation_state"):
            problems.append("bridge routing_key_propagation_state must match fixture")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "changed_service_only_deploy_trace_observed",
        "baseline_fallback_traffic_trace_observed",
        "routing_key_header_propagation_observed",
    ]:
        if claim not in certified:
            problems.append(f"bridge missing certified_claim {claim}")

    non_certified = set(bridge.get("non_certified_claims", []))
    for claim in [
        "signadot_vendor_parity",
        "live_cluster_execution",
        "production_readiness",
        "network_isolation_enforced",
        "service_mesh_runtime_parity",
        "async_stateful_isolation_runtime_observed",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized",
    ]:
        if claim not in non_certified:
            problems.append(f"bridge missing non_certified_claim {claim}")

    forbidden_overlap = certified & non_certified
    if forbidden_overlap:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(forbidden_overlap)}")

    next_required = set(bridge.get("next_required_evidence", []))
    for satisfied in ["baseline_fallback_traffic_trace", "changed_service_only_deploy_trace"]:
        if satisfied in next_required:
            problems.append(f"{satisfied} should be removed from next_required_evidence once linked")

    report = {
        "validator": "prophet-platform.workroom-runtime-baseline-fallback-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks bridge linkage to non-production baseline fallback fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime baseline fallback bridge")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
