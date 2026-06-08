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
    ref = bridge.get("source_records", {}).get("network_isolation_observation_ref")
    if not isinstance(ref, str) or not ref:
        problems.append("missing source_records.network_isolation_observation_ref")
        network = {}
    elif not resolve(ref).exists():
        problems.append(f"network isolation observation ref missing: {ref}")
        network = {}
    else:
        network = load(resolve(ref))

    observed = bridge.get("observed_evidence", {})
    if network:
        obs = network.get("network_policy_observation", {})
        counts = obs.get("packet_counts", {})
        if observed.get("network_isolation_observation_state") != obs.get("state"):
            problems.append("bridge network isolation state must match fixture")
        if observed.get("network_policy_trace_ref") != obs.get("policy_trace_ref"):
            problems.append("bridge network policy trace ref must match fixture")
        for bridge_key, count_key in [
            ("network_allowed_ingress_count", "allowed_ingress"),
            ("network_denied_cross_sandbox_count", "denied_cross_sandbox"),
            ("network_denied_external_egress_count", "denied_external_egress"),
        ]:
            if observed.get(bridge_key) != counts.get(count_key):
                problems.append(f"bridge {bridge_key} must match fixture")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "nonprod_network_policy_fixture_trace_observed",
        "nonprod_allowed_ingress_trace_observed",
        "nonprod_cross_sandbox_denial_trace_observed",
        "nonprod_external_egress_denial_trace_observed",
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

    if certified & non_certified:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(certified & non_certified)}")

    if "network_isolation_observation" in set(bridge.get("next_required_evidence", [])):
        problems.append("network_isolation_observation should be removed from next_required_evidence once linked")

    report = {
        "validator": "prophet-platform.workroom-runtime-network-isolation-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks bridge linkage to non-production network isolation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live network isolation enforcement.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime network isolation bridge")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
