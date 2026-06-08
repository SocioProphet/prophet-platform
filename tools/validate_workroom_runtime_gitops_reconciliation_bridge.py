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
    ref = bridge.get("source_records", {}).get("gitops_reconciliation_observation_ref")
    if not isinstance(ref, str) or not ref:
        problems.append("missing source_records.gitops_reconciliation_observation_ref")
        gitops = {}
    elif not resolve(ref).exists():
        problems.append(f"gitops reconciliation observation ref missing: {ref}")
        gitops = {}
    else:
        gitops = load(resolve(ref))

    observed = bridge.get("observed_evidence", {})
    if gitops:
        obs = gitops.get("gitops_observation", {})
        if observed.get("gitops_reconciliation_observation_state") != obs.get("state"):
            problems.append("bridge gitops state must match fixture")
        if observed.get("gitops_sync_status") != obs.get("sync_status"):
            problems.append("bridge gitops sync status must match fixture")
        if observed.get("gitops_health_status") != obs.get("health_status"):
            problems.append("bridge gitops health status must match fixture")
        if observed.get("gitops_drift_state") != obs.get("drift_detection", {}).get("state"):
            problems.append("bridge gitops drift state must match fixture")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "nonprod_gitops_reconciliation_fixture_trace_observed",
        "nonprod_gitops_sync_trace_observed",
        "nonprod_gitops_health_trace_observed",
        "nonprod_gitops_no_drift_trace_observed",
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
        "gitops_controller_reconciliation_live_certified",
        "live_apply_authorized",
    ]:
        if claim not in non_certified:
            problems.append(f"bridge missing non_certified_claim {claim}")

    if certified & non_certified:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(certified & non_certified)}")

    if "gitops_reconciliation_observation" in set(bridge.get("next_required_evidence", [])):
        problems.append("gitops_reconciliation_observation should be removed from next_required_evidence once linked")

    report = {
        "validator": "prophet-platform.workroom-runtime-gitops-reconciliation-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks bridge linkage to non-production GitOps reconciliation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live GitOps controller reconciliation.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime GitOps reconciliation bridge")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
