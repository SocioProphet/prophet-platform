#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "artifacts" / "runtime" / "workroom-runtime-parity-bridge" / "fogstack-svf-signadot-readiness.bridge.json"
STATUS = ROOT / "docs" / "architecture" / "devsecops-workroom-v0.1-status.md"

REQUIRED_SOURCE_RECORD_KEYS = {
    "nonprod_sandbox_observation_ref",
    "baseline_fallback_trace_ref",
    "network_isolation_observation_ref",
    "async_topic_isolation_observation_ref",
    "stateful_resource_isolation_observation_ref",
    "gitops_reconciliation_observation_ref",
    "leak_check_observation_ref",
}

REQUIRED_FIXTURE_CLAIM_TOKENS = {
    "baseline_fallback",
    "changed_service",
    "network",
    "async",
    "stateful",
    "gitops",
    "leak_check",
}

REQUIRED_BOUNDARY_TOKENS = {
    "vendor",
    "production",
    "service_mesh",
    "live",
}


def main() -> int:
    problems: list[str] = []

    try:
        bridge = json.loads(BRIDGE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERR: failed to load bridge: {exc}", file=sys.stderr)
        return 2

    try:
        status_text = STATUS.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"ERR: failed to load status ledger: {exc}", file=sys.stderr)
        return 2

    if bridge.get("record_type") != "WorkroomRuntimeParityBridge":
        problems.append("bridge record_type mismatch")
    if bridge.get("decision_state") != "nonprod_evidence_ready_but_vendor_parity_blocked":
        problems.append("bridge decision_state must keep the non-production evidence boundary")

    source_records = set(bridge.get("source_records", {}))
    missing_sources = sorted(REQUIRED_SOURCE_RECORD_KEYS - source_records)
    if missing_sources:
        problems.append(f"missing required source records: {missing_sources}")

    certified_blob = "\n".join(bridge.get("certified_claims", [])).lower()
    for token in REQUIRED_FIXTURE_CLAIM_TOKENS:
        if token not in certified_blob:
            problems.append(f"certified fixture claims missing token: {token}")

    non_certified_blob = "\n".join(bridge.get("non_certified_claims", [])).lower()
    for token in REQUIRED_BOUNDARY_TOKENS:
        if token not in non_certified_blob:
            problems.append(f"non-certified claim boundaries missing token: {token}")

    non_claims_blob = "\n".join(bridge.get("non_claims", [])).lower()
    if "does not" not in non_claims_blob:
        problems.append("bridge non_claims must preserve explicit negative claim language")
    if "certify" not in non_claims_blob:
        problems.append("bridge non_claims must preserve certification boundary language")

    for required_status_phrase in (
        "P2 Runtime Parity Fixture Evidence Matrix",
        "non-production fixture observations",
        "not a live runtime parity certification",
    ):
        if required_status_phrase not in status_text:
            problems.append(f"status ledger missing phrase: {required_status_phrase}")

    result = {
        "validator": "prophet-platform.devsecops-workroom-demo-readiness.validator.v1",
        "bridge": str(BRIDGE.relative_to(ROOT)),
        "status_ledger": str(STATUS.relative_to(ROOT)),
        "passed": not problems,
        "problems": problems,
        "readiness_state": "ready_for_nonprod_fixture_review" if not problems else "blocked",
        "non_claims": [
            "Validator checks existing fixture evidence and claim boundaries only.",
            "Validator does not perform external runtime operations.",
            "Validator does not certify production readiness.",
            "Validator does not certify external vendor feature parity."
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    if problems:
        print("FAIL: DevSecOps Workroom demo readiness", file=sys.stderr)
        return 2

    print("PASS: DevSecOps Workroom demo readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
