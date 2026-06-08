#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts" / "runtime" / "gitops-reconciliation-observation" / "fogstack-svf-gitops-reconciliation-observed.v0.1.json"

def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data

def main() -> int:
    problems: list[str] = []
    data = load(FIXTURE)

    if data.get("record_type") != "FogStackSVFGitOpsReconciliationObservation":
        problems.append("record_type mismatch")
    if data.get("observation_scope") != "nonprod_fixture_observation":
        problems.append("observation_scope must be nonprod_fixture_observation")

    obs = data.get("gitops_observation", {})
    if obs.get("state") != "observed_fixture_reconciliation_trace_only":
        problems.append("gitops observation state must be observed_fixture_reconciliation_trace_only")
    if obs.get("desired_revision") != obs.get("observed_revision"):
        problems.append("desired_revision must equal observed_revision")
    if obs.get("sync_status") != "Synced":
        problems.append("sync_status must be Synced")
    if obs.get("health_status") != "Healthy":
        problems.append("health_status must be Healthy")
    if not obs.get("reconciliation_trace_ref"):
        problems.append("reconciliation_trace_ref is required")

    events = obs.get("reconciliation_events", [])
    required_events = {"application_detected", "sync_complete", "health_healthy"}
    event_types = {e.get("event_type") for e in events if isinstance(e, dict)}
    if missing := sorted(required_events - event_types):
        problems.append(f"missing reconciliation events: {missing}")
    for idx, event in enumerate(events):
        if event.get("result") != "observed":
            problems.append(f"reconciliation_events[{idx}].result must be observed")
        if not event.get("evidence_ref"):
            problems.append(f"reconciliation_events[{idx}].evidence_ref is required")

    drift = obs.get("drift_detection", {})
    if drift.get("state") != "observed_no_drift":
        problems.append("drift state must be observed_no_drift")
    if drift.get("desired_hash") != drift.get("observed_hash"):
        problems.append("desired_hash must equal observed_hash")
    if not drift.get("evidence_ref"):
        problems.append("drift evidence_ref is required")

    policy = data.get("policy_boundary", {})
    for key in ["live_apply_authorized", "cluster_mutation_authorized", "production_environment", "secret_access_authorized"]:
        if policy.get(key) is not False:
            problems.append(f"policy_boundary.{key} must be false")
    if policy.get("human_approval_required_for_live_apply") is not True:
        problems.append("human approval must be required for live apply")

    certified = set(data.get("certified_claims", []))
    required_certified = {
        "nonprod_gitops_reconciliation_fixture_trace_observed",
        "nonprod_gitops_sync_trace_observed",
        "nonprod_gitops_health_trace_observed",
        "nonprod_gitops_no_drift_trace_observed",
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
        "gitops_controller_reconciliation_live_certified",
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
        "does not certify live gitops controller reconciliation",
        "does not certify full signadot-style feature parity"
    ]:
        if not all(word in non_claim_text for word in phrase.split()):
            problems.append(f"non_claims missing posture {phrase!r}")

    report = {
        "validator": "prophet-platform.fogstack-svf-gitops-reconciliation-observation.validator.v1",
        "passed": not problems,
        "problems": problems,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks a non-production GitOps reconciliation fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live GitOps controller reconciliation.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": FogStack SVF GitOps reconciliation observation")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
