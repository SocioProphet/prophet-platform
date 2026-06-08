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
    ref = bridge.get("source_records", {}).get("stateful_resource_isolation_observation_ref")
    if not isinstance(ref, str) or not ref:
        problems.append("missing source_records.stateful_resource_isolation_observation_ref")
        stateful = {}
    elif not resolve(ref).exists():
        problems.append(f"stateful resource isolation observation ref missing: {ref}")
        stateful = {}
    else:
        stateful = load(resolve(ref))

    observed = bridge.get("observed_evidence", {})
    if stateful:
        obs = stateful.get("stateful_observation", {})
        if observed.get("stateful_resource_isolation_observation_state") != obs.get("state"):
            problems.append("bridge stateful state must match fixture")
        if observed.get("stateful_resource_trace_ref") != obs.get("resource_trace_ref"):
            problems.append("bridge stateful resource trace ref must match fixture")
        if observed.get("stateful_allocated_resource_count") != len(obs.get("allocated_resource_refs", [])):
            problems.append("bridge stateful allocated resource count must match fixture")
        if observed.get("stateful_cross_sandbox_denied_count") != len(obs.get("denied_cross_sandbox_resource_refs", [])):
            problems.append("bridge stateful cross-sandbox denial count must match fixture")
        if observed.get("stateful_baseline_mutation_denied_count") != len(obs.get("denied_baseline_resource_mutations", [])):
            problems.append("bridge stateful baseline mutation denial count must match fixture")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "nonprod_stateful_resource_fixture_trace_observed",
        "nonprod_ephemeral_resource_allocation_trace_observed",
        "nonprod_cross_sandbox_resource_denial_trace_observed",
        "nonprod_baseline_resource_mutation_denial_trace_observed",
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
        "stateful_resource_isolation_runtime_enforced",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized",
    ]:
        if claim not in non_certified:
            problems.append(f"bridge missing non_certified_claim {claim}")

    if certified & non_certified:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(certified & non_certified)}")

    if "stateful_resource_isolation_observation" in set(bridge.get("next_required_evidence", [])):
        problems.append("stateful_resource_isolation_observation should be removed from next_required_evidence once linked")

    report = {
        "validator": "prophet-platform.workroom-runtime-stateful-resource-isolation-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks bridge linkage to non-production stateful resource isolation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live stateful resource isolation enforcement.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime stateful resource isolation bridge")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
