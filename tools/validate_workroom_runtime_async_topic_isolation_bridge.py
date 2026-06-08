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
    ref = bridge.get("source_records", {}).get("async_topic_isolation_observation_ref")
    if not isinstance(ref, str) or not ref:
        problems.append("missing source_records.async_topic_isolation_observation_ref")
        async_obs = {}
    elif not resolve(ref).exists():
        problems.append(f"async topic isolation observation ref missing: {ref}")
        async_obs = {}
    else:
        async_obs = load(resolve(ref))

    observed = bridge.get("observed_evidence", {})
    if async_obs:
        obs = async_obs.get("async_observation", {})
        if observed.get("async_topic_isolation_observation_state") != obs.get("state"):
            problems.append("bridge async topic state must match fixture")
        if observed.get("async_topic_trace_ref") != obs.get("topic_trace_ref"):
            problems.append("bridge async topic trace ref must match fixture")
        expected_allowed = sum(x["message_count"] for x in obs.get("allowed_topic_refs", []))
        expected_cross = sum(x["message_count"] for x in obs.get("denied_cross_sandbox_topic_refs", []))
        expected_baseline = sum(x["message_count"] for x in obs.get("denied_baseline_topic_mutations", []))
        if observed.get("async_allowed_topic_message_count") != expected_allowed:
            problems.append("bridge async_allowed_topic_message_count must match fixture")
        if observed.get("async_cross_sandbox_denied_message_count") != expected_cross:
            problems.append("bridge async_cross_sandbox_denied_message_count must match fixture")
        if observed.get("async_baseline_topic_denied_message_count") != expected_baseline:
            problems.append("bridge async_baseline_topic_denied_message_count must match fixture")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "nonprod_async_topic_fixture_trace_observed",
        "nonprod_allowed_topic_trace_observed",
        "nonprod_cross_sandbox_topic_denial_trace_observed",
        "nonprod_baseline_topic_mutation_denial_trace_observed",
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
        "async_queue_topic_runtime_isolation_enforced",
        "stateful_resource_isolation_observed",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized",
    ]:
        if claim not in non_certified:
            problems.append(f"bridge missing non_certified_claim {claim}")

    if certified & non_certified:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(certified & non_certified)}")

    if "async_queue_topic_isolation_observation" in set(bridge.get("next_required_evidence", [])):
        problems.append("async_queue_topic_isolation_observation should be removed from next_required_evidence once linked")

    report = {
        "validator": "prophet-platform.workroom-runtime-async-topic-isolation-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks bridge linkage to non-production async topic isolation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live async queue or topic isolation enforcement.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime async topic isolation bridge")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
