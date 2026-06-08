#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts" / "runtime" / "async-isolation-observation" / "fogstack-svf-async-topic-isolation-observed.v0.1.json"

def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data

def main() -> int:
    problems: list[str] = []
    data = load(FIXTURE)

    if data.get("record_type") != "FogStackSVFAsyncTopicIsolationObservation":
        problems.append("record_type mismatch")
    if data.get("observation_scope") != "nonprod_fixture_observation":
        problems.append("observation_scope must be nonprod_fixture_observation")
    if not str(data.get("workroom_ref", "")).startswith("workroom:devsecops:runtime-parity:"):
        problems.append("workroom_ref shape mismatch")

    obs = data.get("async_observation", {})
    if obs.get("state") != "observed_fixture_topic_isolation_trace_only":
        problems.append("async observation state must be observed_fixture_topic_isolation_trace_only")
    if not obs.get("topic_trace_ref"):
        problems.append("topic_trace_ref is required")
    for key in ["allowed_topic_refs", "denied_cross_sandbox_topic_refs", "denied_baseline_topic_mutations"]:
        entries = obs.get(key)
        if not isinstance(entries, list) or not entries:
            problems.append(f"{key} must be a non-empty list")
            continue
        for idx, entry in enumerate(entries):
            if not entry.get("evidence_ref"):
                problems.append(f"{key}[{idx}].evidence_ref is required")
            if not isinstance(entry.get("message_count"), int) or entry.get("message_count") <= 0:
                problems.append(f"{key}[{idx}].message_count must be positive")

    visibility = obs.get("consumer_visibility", {})
    if visibility.get("sandbox_consumer_seen_messages") != sum(x["message_count"] for x in obs.get("allowed_topic_refs", [])):
        problems.append("sandbox consumer visibility must match allowed topic message count")
    for key in ["baseline_consumer_seen_messages", "cross_sandbox_consumer_seen_messages"]:
        if visibility.get(key) != 0:
            problems.append(f"{key} must remain 0")

    policy = data.get("policy_boundary", {})
    for key in ["live_apply_authorized", "cluster_mutation_authorized", "production_environment", "secret_access_authorized"]:
        if policy.get(key) is not False:
            problems.append(f"policy_boundary.{key} must be false")
    if policy.get("human_approval_required_for_live_apply") is not True:
        problems.append("human approval must be required for live apply")

    certified = set(data.get("certified_claims", []))
    required_certified = {
        "nonprod_async_topic_fixture_trace_observed",
        "nonprod_allowed_topic_trace_observed",
        "nonprod_cross_sandbox_topic_denial_trace_observed",
        "nonprod_baseline_topic_mutation_denial_trace_observed",
        "receipt_ref_present"
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
        "async_queue_topic_runtime_isolation_enforced",
        "stateful_resource_isolation_observed",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized"
    }
    if missing := sorted(required_non_certified - non_certified):
        problems.append(f"missing non-certified claims: {missing}")
    if overlap := sorted(certified & non_certified):
        problems.append(f"claims cannot be both certified and non-certified: {overlap}")

    if not data.get("receipt_ref"):
        problems.append("receipt_ref is required")

    non_claim_text = "\n".join(str(item) for item in data.get("non_claims", [])).lower()
    for phrase in [
        "does not call signadot",
        "does not authorize live apply",
        "does not authorize cluster mutation",
        "does not certify production readiness",
        "does not certify live async queue or topic isolation enforcement",
        "does not certify full signadot-style feature parity"
    ]:
        if not all(word in non_claim_text for word in phrase.split()):
            problems.append(f"non_claims missing posture {phrase!r}")

    report = {
        "validator": "prophet-platform.fogstack-svf-async-topic-isolation-observation.validator.v1",
        "passed": not problems,
        "problems": problems,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks a non-production async topic isolation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live async queue or topic isolation enforcement.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": FogStack SVF async topic isolation observation")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
