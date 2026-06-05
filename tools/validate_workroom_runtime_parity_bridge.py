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
    refs = bridge.get("source_records", {})

    required_refs = [
        "fogstack_parity_record_ref",
        "fogstack_summary_ref",
        "fogstack_artifact_index_ref",
        "svf_signadot_adapter_readiness_ref",
        "policy_simulation_contract_ref",
        "nonprod_sandbox_observation_ref",
    ]
    for key in required_refs:
        ref = refs.get(key)
        if not isinstance(ref, str) or not ref:
            problems.append(f"missing source_records.{key}")
            continue
        if not resolve(ref).exists():
            problems.append(f"source_records.{key} does not exist: {ref}")

    if problems:
        return finish(problems)

    fogstack = load(resolve(refs["fogstack_parity_record_ref"]))
    svf = load(resolve(refs["svf_signadot_adapter_readiness_ref"]))
    nonprod = load(resolve(refs["nonprod_sandbox_observation_ref"]))
    observed = bridge.get("observed_evidence", {})

    if bridge.get("record_type") != "WorkroomRuntimeParityBridge":
        problems.append("record_type must be WorkroomRuntimeParityBridge")
    if not str(bridge.get("bridge_id", "")).startswith("workroom-runtime-parity-bridge:"):
        problems.append("bridge_id shape is invalid")
    if not str(bridge.get("workroom_ref", "")).startswith("workroom:devsecops:runtime-parity:"):
        problems.append("workroom_ref shape is invalid")

    if fogstack.get("status") != "passed":
        problems.append("FogStack parity record must be passed")
    if fogstack.get("errors") != []:
        problems.append("FogStack parity record errors must be empty")
    if observed.get("fogstack_parity_status") != fogstack.get("status"):
        problems.append("bridge fogstack_parity_status must match parity record")
    if observed.get("fogstack_parity_target") != fogstack.get("parity_target"):
        problems.append("bridge fogstack_parity_target must match parity record")

    checked = {item.get("id"): item.get("status") for item in fogstack.get("checked_lanes", []) if isinstance(item, dict)}
    expected_lanes = {
        "node_inventory": "passed",
        "immutable_update_readiness": "passed",
        "cluster_readiness": "passed",
        "gitops_readiness": "passed",
        "live_cluster_preflight": "blocked",
        "live_apply_plan": "blocked",
        "runtime_adapter": "passed",
        "runtime_dry_run": "passed",
    }
    bridge_lanes = observed.get("fogstack_checked_lanes", {})
    for lane, status in expected_lanes.items():
        if checked.get(lane) != status:
            problems.append(f"FogStack parity record lane {lane} expected {status}, got {checked.get(lane)}")
        if bridge_lanes.get(lane) != status:
            problems.append(f"bridge lane {lane} expected {status}, got {bridge_lanes.get(lane)}")

    adapter = svf.get("adapter_readiness", {})
    if adapter.get("status") != "not_vendor_certified":
        problems.append("SVF adapter readiness must remain not_vendor_certified")
    if adapter.get("merge_readiness") != "blocked_for_vendor_parity_claims":
        problems.append("SVF adapter merge readiness must block vendor parity claims")
    if observed.get("svf_adapter_readiness_status") != adapter.get("status"):
        problems.append("bridge SVF adapter status must match fixture")
    if observed.get("svf_adapter_merge_readiness") != adapter.get("merge_readiness"):
        problems.append("bridge SVF adapter merge readiness must match fixture")

    if nonprod.get("record_type") != "FogStackSVFNonprodSandboxObservation":
        problems.append("nonprod observation record_type mismatch")
    if nonprod.get("observation_scope") != "nonprod_fixture_observation":
        problems.append("nonprod observation scope mismatch")
    lease = nonprod.get("sandbox_lease", {})
    job = nonprod.get("validation_job", {})
    routing = nonprod.get("routing", {})
    if observed.get("nonprod_sandbox_observation_state") != "nonprod_fixture_observed":
        problems.append("bridge nonprod observation state mismatch")
    if observed.get("nonprod_sandbox_lease_state") != lease.get("lease_state"):
        problems.append("bridge nonprod lease state must match observation")
    if observed.get("nonprod_validation_job_state") != job.get("job_state"):
        problems.append("bridge nonprod validation job state must match observation")
    if observed.get("nonprod_teardown_state") != lease.get("teardown_state"):
        problems.append("bridge nonprod teardown state must match observation")
    if observed.get("baseline_fallback_state") != routing.get("baseline_fallback_state"):
        problems.append("bridge baseline fallback state must match observation")

    non_certified = set(bridge.get("non_certified_claims", []))
    for claim in [
        "signadot_vendor_parity",
        "live_cluster_execution",
        "production_readiness",
        "network_isolation_enforced",
        "service_mesh_runtime_parity",
        "baseline_fallback_traffic_proven",
        "async_stateful_isolation_runtime_observed",
        "gitops_controller_reconciliation_observed",
        "live_apply_authorized",
    ]:
        if claim not in non_certified:
            problems.append(f"bridge missing non_certified_claim {claim}")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "nonprod_sandbox_lease_observed_created",
        "nonprod_validation_job_observed_passed",
        "nonprod_teardown_or_expiry_observed",
        "nonprod_receipt_ref_present",
    ]:
        if claim not in certified:
            problems.append(f"bridge missing certified_claim {claim}")
    forbidden = certified & non_certified
    if forbidden:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(forbidden)}")

    if bridge.get("decision_state") != "nonprod_evidence_ready_but_vendor_parity_blocked":
        problems.append("decision_state must remain nonprod_evidence_ready_but_vendor_parity_blocked")

    non_claim_text = "\n".join(str(item) for item in bridge.get("non_claims", [])).lower()
    for phrase in [
        "does not call signadot",
        "does not execute kubernetes workloads",
        "does not mutate a cluster",
        "does not authorize live apply",
        "does not certify full signadot-style feature parity",
    ]:
        if not all(word in non_claim_text for word in phrase.split()):
            problems.append(f"bridge non_claims missing posture {phrase!r}")

    return finish(problems)


def finish(problems: list[str]) -> int:
    report = {
        "validator": "prophet-platform.workroom-runtime-parity-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks persisted runtime-adjacent evidence and bridge claim boundaries only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not mutate a cluster.",
            "Validator does not authorize live apply.",
            "Validator does not certify full Signadot-style feature parity."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime parity bridge")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
