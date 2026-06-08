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
    ref = bridge.get("source_records", {}).get("leak_check_observation_ref")
    if not isinstance(ref, str) or not ref:
        problems.append("missing source_records.leak_check_observation_ref")
        leak = {}
    elif not resolve(ref).exists():
        problems.append(f"leak-check observation ref missing: {ref}")
        leak = {}
    else:
        leak = load(resolve(ref))

    observed = bridge.get("observed_evidence", {})
    if leak:
        obs = leak.get("leak_check_observation", {})
        if observed.get("leak_check_observation_state") != obs.get("state"):
            problems.append("bridge leak-check state must match fixture")
        if observed.get("leak_check_trace_ref") != obs.get("leak_check_trace_ref"):
            problems.append("bridge leak-check trace ref must match fixture")
        if observed.get("leak_check_residual_count") != sum(check.get("residual_count", 0) for check in obs.get("checks", [])):
            problems.append("bridge leak_check_residual_count must match fixture")

    certified = set(bridge.get("certified_claims", []))
    for claim in [
        "nonprod_leak_check_fixture_trace_observed",
        "nonprod_no_orphaned_routes_trace_observed",
        "nonprod_no_orphaned_async_topics_trace_observed",
        "nonprod_no_orphaned_stateful_resources_trace_observed",
        "nonprod_no_orphaned_secrets_trace_observed",
        "nonprod_no_orphaned_network_policies_trace_observed",
    ]:
        if claim not in certified:
            problems.append(f"bridge missing certified_claim {claim}")

    non_certified = set(bridge.get("non_certified_claims", []))
    for claim in [
        "signadot_vendor_parity",
        "live_cluster_execution",
        "production_readiness",
        "live_leak_free_runtime_certified",
        "live_apply_authorized",
    ]:
        if claim not in non_certified:
            problems.append(f"bridge missing non_certified_claim {claim}")

    if certified & non_certified:
        problems.append(f"claims cannot be both certified and non-certified: {sorted(certified & non_certified)}")

    if "leak_check_observation" in set(bridge.get("next_required_evidence", [])):
        problems.append("leak_check_observation should be removed from next_required_evidence once linked")

    report = {
        "validator": "prophet-platform.workroom-runtime-leak-check-bridge.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "non_claims": [
            "Validator checks bridge linkage to non-production leak-check fixture only.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not authorize live apply.",
            "Validator does not certify live leak-free runtime cleanup.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime leak-check bridge")
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
