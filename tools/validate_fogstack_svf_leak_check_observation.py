#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts" / "runtime" / "leak-check-observation" / "fogstack-svf-leak-check-observed.v0.1.json"

def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data

def main() -> int:
    problems: list[str] = []
    data = load(FIXTURE)

    if data.get("record_type") != "FogStackSVFLeakCheckObservation":
        problems.append("record_type mismatch")
    if data.get("observation_scope") != "nonprod_fixture_observation":
        problems.append("observation_scope must be nonprod_fixture_observation")
    if not data.get("teardown_evidence_ref"):
        problems.append("teardown_evidence_ref is required")

    obs = data.get("leak_check_observation", {})
    if obs.get("state") != "observed_fixture_leak_check_trace_only":
        problems.append("leak check state must be observed_fixture_leak_check_trace_only")
    if not obs.get("leak_check_trace_ref"):
        problems.append("leak_check_trace_ref is required")

    checks = obs.get("checks", [])
    required_classes = {"route", "topic", "stateful_resource", "secret", "network_policy"}
    seen_classes = {check.get("resource_class") for check in checks if isinstance(check, dict)}
    if missing := sorted(required_classes - seen_classes):
        problems.append(f"missing leak-check resource classes: {missing}")
    for idx, check in enumerate(checks):
        if check.get("result") != "none_found":
            problems.append(f"checks[{idx}].result must be none_found")
        if check.get("residual_count") != 0:
            problems.append(f"checks[{idx}].residual_count must be 0")
        if not check.get("evidence_ref"):
            problems.append(f"checks[{idx}].evidence_ref is required")

    policy = data.get("policy_boundary", {})
    for key in ["live_apply_authorized", "cluster_mutation_authorized", "production_environment", "secret_access_authorized"]:
        if policy.get(key) is not False:
            problems.append(f"policy_boundary.{key} must be false")
    if policy.get("human_approval_required_for_live_apply") is not True:
        problems.append("human approval must be required for live apply")

    certified = set(data.get("certified_claims", []))
    required_certified = {
        "nonprod_leak_check_fixture_trace_observed",
        "nonprod_no_orphaned_routes_trace_observed",
        "nonprod_no_orphaned_async_topics_trace_observed",
        "nonprod_no_orphaned_stateful_resources_trace_observed",
        "nonprod_no_orphaned_secrets_trace_observed",
        "nonprod_no_orphaned_network_policies_trace_observed",
        "receipt_ref_present"
    }
    if missing := sorted(required_certified - certified):
        problems.append(f"missing certified claims: {missing}")

    non_certified = set(data.get("non_certified_claims", []))
    required_non_certified = {
        "signadot_vendor_parity",
        "production_readiness",
        "live_cluster_execution",
        "live_leak_free_runtime_certified",
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
        "does not certify live leak-free runtime cleanup",
        "does not certify full signadot-style feature parity"
    ]:
        if not all(word in non_claim_text for word in phrase.split()):
            problems.append(f"non_claims missing posture {phrase!r}")

    report = {
        "validator": "prophet-platform.fogstack-svf-leak-check-observation.validator.v1",
        "passed": not problems,
        "problems": problems,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks a non-production leak-check fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live leak-free runtime cleanup.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": FogStack SVF leak-check observation")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
