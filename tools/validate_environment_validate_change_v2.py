#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "contracts" / "environment" / "validate-change-v2-request.example.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-requested.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.selected-only.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-failed.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.stale-receipt.json",
]
STATUSES = {
    "environment_requested",
    "environment_observed",
    "environment_failed",
}
VALIDATION_EVIDENCE_STATES = {
    "not_configured",
    "selected_only",
    "missing_evidence",
    "synthetic_observed",
    "runtime_observed",
    "verified_receipt",
    "failed_receipt",
    "stale_receipt",
}
MERGE_READY_STATES = {"verified_receipt"}
BLOCKING_STATES = {"not_configured", "selected_only", "missing_evidence", "failed_receipt", "stale_receipt"}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture must be an object: {path}")
    return data


def check(check_id: str, passed: bool, diagnostics: list[str] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "diagnostics": diagnostics or []}


def validate_request(data: dict[str, Any]) -> list[dict[str, Any]]:
    env = data.get("environment_request", {})
    execution = data.get("execution", {})
    sociosphere = data.get("sociosphere_refs", {})
    return [
        check("request:schema-version", data.get("schema_version") == "1.0"),
        check("request:id", str(data.get("request_id", "")).startswith("environment:validate-change-v2-request:")),
        check("request:repo", "/" in str(data.get("repo", ""))),
        check("request:changed-paths", isinstance(data.get("changed_paths"), list) and len(data.get("changed_paths", [])) > 0),
        check("request:change-digest", isinstance(data.get("change_digest"), dict) and data["change_digest"].get("algorithm") in {"sha256", "sha512"}),
        check("request:sociosphere-profile", str(sociosphere.get("environment_profile_id", "")).startswith("environment-sandbox:profile:")),
        check("request:selected-plans", isinstance(data.get("selected_plans"), list) and len(data.get("selected_plans", [])) > 0),
        check("request:baseline-ref", str(env.get("baseline_ref", "")).startswith("workspace://")),
        check("request:changed-service-refs", isinstance(env.get("changed_service_refs"), list)),
        check("request:synthetic-isolation", env.get("requested_isolation_class") == "synthetic_no_network", [str(env.get("requested_isolation_class"))]),
        check("request:executor-plane", execution.get("executor_plane") == "AgentPlane", [str(execution.get("executor_plane"))]),
        check("request:evidence-required", execution.get("evidence_required") is True),
        check("request:non-claims", isinstance(data.get("non_claims"), list) and len(data.get("non_claims", [])) >= 1),
    ]


def validate_pr_readiness(data: dict[str, Any], evidence_state: str | None) -> list[dict[str, Any]]:
    readiness = data.get("pr_readiness", {})
    blocking_codes = readiness.get("blocking_reason_codes", []) if isinstance(readiness, dict) else []
    merge_allowed = readiness.get("merge_allowed") if isinstance(readiness, dict) else None
    readiness_state = readiness.get("readiness_state") if isinstance(readiness, dict) else None
    results = [
        check("readiness:object", isinstance(readiness, dict) and bool(readiness), [str(readiness)]),
        check("readiness:required-state", readiness.get("required_evidence_state") == "verified_receipt" if isinstance(readiness, dict) else False),
        check("readiness:non-claims", isinstance(readiness.get("non_claims"), list) and len(readiness.get("non_claims", [])) >= 1 if isinstance(readiness, dict) else False),
    ]
    if evidence_state in MERGE_READY_STATES:
        results.extend([
            check("readiness:verified:merge-allowed", merge_allowed is True, [str(merge_allowed)]),
            check("readiness:verified:state", readiness_state == "ready", [str(readiness_state)]),
            check("readiness:verified:no-blocking-codes", blocking_codes == [], [str(blocking_codes)]),
        ])
    if evidence_state in BLOCKING_STATES:
        results.extend([
            check(f"readiness:{evidence_state}:merge-blocked", merge_allowed is False, [str(merge_allowed)]),
            check(f"readiness:{evidence_state}:not-ready", readiness_state in {"blocked", "needs_review"}, [str(readiness_state)]),
            check(f"readiness:{evidence_state}:blocking-codes", isinstance(blocking_codes, list) and len(blocking_codes) >= 1, [str(blocking_codes)]),
        ])
    return results


def validate_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    status = data.get("status")
    execution = data.get("agentplane_execution", {})
    evidence_refs = execution.get("evidence_refs", [])
    evidence_summary = data.get("evidence_summary", {})
    receipt_refs = evidence_summary.get("receipt_refs", []) if isinstance(evidence_summary, dict) else []
    failure_codes = evidence_summary.get("failure_codes", []) if isinstance(evidence_summary, dict) else []
    evidence_state = evidence_summary.get("validation_evidence_state") if isinstance(evidence_summary, dict) else None
    results = [
        check(f"response:{status}:schema-version", data.get("schema_version") == "1.0"),
        check(f"response:{status}:status", status in STATUSES, [str(status)]),
        check(f"response:{status}:repo", "/" in str(data.get("repo", ""))),
        check(f"response:{status}:selected-plans", isinstance(data.get("selected_plans"), list) and len(data.get("selected_plans", [])) > 0),
        check(f"response:{status}:executor-plane", execution.get("executor_plane") == "AgentPlane", [str(execution.get("executor_plane"))]),
        check(f"response:{status}:sandbox-run-ref", str(execution.get("sandbox_run_ref", "")).startswith("agentplane:sandbox-run:")),
        check(f"response:{status}:evidence-refs-list", isinstance(evidence_refs, list)),
        check(f"response:{status}:evidence-summary", isinstance(evidence_summary, dict) and bool(evidence_summary), [str(evidence_summary)]),
        check(f"response:{status}:validation-evidence-state", evidence_state in VALIDATION_EVIDENCE_STATES, [str(evidence_state)]),
        check(f"response:{status}:non-claims", isinstance(data.get("non_claims"), list) and len(data.get("non_claims", [])) >= 1),
    ]
    results.extend(validate_pr_readiness(data, evidence_state))

    if status == "environment_requested":
        results.extend([
            check("response:requested:execution-status", execution.get("execution_status") == "requested"),
            check("response:requested:evidence-empty", evidence_refs == [], [str(evidence_refs)]),
            check("response:requested:non-ready-state", evidence_state in {"selected_only", "missing_evidence"}, [str(evidence_state)]),
            check("response:requested:missing-warning", "environment_execution_not_observed" in data.get("warnings", []), [str(data.get("warnings", []))]),
        ])
    if status == "environment_observed":
        results.extend([
            check("response:observed:execution-status", execution.get("execution_status") == "observed"),
            check("response:observed:evidence-present", len(evidence_refs) >= 1, [str(evidence_refs)]),
            check("response:observed:verified-receipt-state", evidence_state == "verified_receipt", [str(evidence_state)]),
            check("response:observed:receipt-present", isinstance(receipt_refs, list) and len(receipt_refs) >= 1, [str(receipt_refs)]),
            check("response:observed:svf-receipt", all(str(ref).startswith("svf:receipt:") for ref in receipt_refs), [str(receipt_refs)]),
            check("response:observed:no-warnings", data.get("warnings") == [], [str(data.get("warnings"))]),
        ])
    if status == "environment_failed":
        results.extend([
            check("response:failed:execution-status", execution.get("execution_status") == "failed"),
            check("response:failed:evidence-state", evidence_state in {"failed_receipt", "stale_receipt"}, [str(evidence_state)]),
            check("response:failed:evidence-present", len(evidence_refs) >= 1, [str(evidence_refs)]),
            check("response:failed:failure-code", any(code in failure_codes for code in {"svf_receipt_failed", "svf_receipt_stale", "synthetic_validation_failed"}), [str(failure_codes)]),
            check("response:failed:warning", any(warning in data.get("warnings", []) for warning in {"environment_validation_failed", "validation_receipt_failed", "validation_receipt_stale"}), [str(data.get("warnings", []))]),
        ])
    return results


def main() -> int:
    results: list[dict[str, Any]] = []
    for path in FIXTURES:
        data = load(path)
        if "environment_request" in data:
            results.extend(validate_request(data))
        else:
            results.extend(validate_response(data))
    passed = all(item["passed"] for item in results)
    print(json.dumps({"validator": "prophet-platform.validate-change-v2.environment.validator.v1", "passed": passed, "results": results}, indent=2, sort_keys=True))
    print(("PASS" if passed else "FAIL") + ": validate_change v2 environment fixtures")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
