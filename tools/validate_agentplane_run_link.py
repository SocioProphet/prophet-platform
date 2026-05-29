#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LINK = ROOT / "contracts" / "environment" / "validate-change-v2-agentplane-run-link.example.json"
REQUESTED = ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-requested.json"
OBSERVED = ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json"
FAILED = ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-failed.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def main() -> int:
    problems: list[str] = []
    link = load(LINK)
    requested = load(REQUESTED)
    observed = load(OBSERVED)
    failed = load(FAILED)

    if link.get("schema_version") != "1.0":
        problems.append("link schema_version must be 1.0")
    if not str(link.get("link_id", "")).startswith("environment:validate-change-v2-agentplane-link:"):
        problems.append("link_id shape is invalid")
    if not str(link.get("request_id", "")).startswith("environment:validate-change-v2-request:"):
        problems.append("request_id must reference validate_change v2 request")

    mapping = link.get("status_mapping", {})
    if mapping.get("environment_requested") != "sandbox_requested":
        problems.append("environment_requested must map to sandbox_requested")
    if mapping.get("environment_observed") != "sandbox_observed":
        problems.append("environment_observed must map to sandbox_observed")

    boundary = link.get("execution_boundary", {})
    if boundary.get("executor_plane") != "AgentPlane":
        problems.append("executor_plane must be AgentPlane")
    if boundary.get("execution_mode") != "synthetic_fixture":
        problems.append("execution_mode must be synthetic_fixture")
    if boundary.get("requested_isolation_class") != "synthetic_no_network":
        problems.append("requested_isolation_class must be synthetic_no_network")
    if boundary.get("runtime_parity_status") != "not_certified":
        problems.append("runtime parity must remain not_certified")

    run_refs = link.get("agentplane_run_refs", {})
    for key in ("requested", "observed"):
        if not str(run_refs.get(key, "")).startswith("agentplane:sandbox-run:"):
            problems.append(f"agentplane_run_refs.{key} must reference sandbox run")

    response_refs = link.get("prophet_platform_response_refs", {})
    if response_refs.get("requested") != requested.get("response_id"):
        problems.append("requested response ref does not match requested fixture")
    if response_refs.get("observed") != observed.get("response_id"):
        problems.append("observed response ref does not match observed fixture")

    observed_exec = observed.get("agentplane_execution", {})
    evidence_mapping = link.get("evidence_mapping", {})
    if evidence_mapping.get("observed_evidence_ref") not in observed_exec.get("evidence_refs", []):
        problems.append("observed evidence ref must match observed response fixture")
    observed_receipts = observed.get("evidence_summary", {}).get("receipt_refs", [])
    if evidence_mapping.get("observed_receipt_ref") not in observed_receipts:
        problems.append("observed receipt ref must match observed response fixture")

    # The failed response fixture must remain available even while this initial link only binds requested/observed.
    if failed.get("status") != "environment_failed":
        problems.append("failed fixture must remain environment_failed for next mapping tranche")

    non_claims = link.get("non_claims", [])
    if not isinstance(non_claims, list) or len(non_claims) < 2:
        problems.append("link must include non_claims")

    report = {
        "validator": "prophet-platform.validate-change-v2.agentplane-run-link.v1",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Validator checks synthetic run-link semantics only.",
            "Validator does not execute infrastructure.",
            "Validator does not certify runtime parity."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": validate_change v2 AgentPlane run link")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
