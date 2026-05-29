#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "contracts" / "environment" / "validate-change-v2-request.example.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-requested.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json",
    ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-failed.json",
]
STATUSES = {
    "environment_requested",
    "environment_observed",
    "environment_failed",
}


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


def validate_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    status = data.get("status")
    execution = data.get("agentplane_execution", {})
    evidence_refs = execution.get("evidence_refs", [])
    evidence_summary = data.get("evidence_summary", {})
    results = [
        check(f"response:{status}:schema-version", data.get("schema_version") == "1.0"),
        check(f"response:{status}:status", status in STATUSES, [str(status)]),
        check(f"response:{status}:repo", "/" in str(data.get("repo", ""))),
        check(f"response:{status}:selected-plans", isinstance(data.get("selected_plans"), list) and len(data.get("selected_plans", [])) > 0),
        check(f"response:{status}:executor-plane", execution.get("executor_plane") == "AgentPlane", [str(execution.get("executor_plane"))]),
        check(f"response:{status}:sandbox-run-ref", str(execution.get("sandbox_run_ref", "")).startswith("agentplane:sandbox-run:")),
        check(f"response:{status}:evidence-refs-list", isinstance(evidence_refs, list)),
        check(f"response:{status}:non-claims", isinstance(data.get("non_claims"), list) and len(data.get("non_claims", [])) >= 1),
    ]
    if status == "environment_requested":
        results.extend([
            check("response:requested:execution-status", execution.get("execution_status") == "requested"),
            check("response:requested:evidence-empty", evidence_refs == [], [str(evidence_refs)]),
            check("response:requested:missing-warning", "environment_execution_not_observed" in data.get("warnings", []), [str(data.get("warnings", []))]),
        ])
    if status == "environment_observed":
        receipt_refs = evidence_summary.get("receipt_refs", []) if isinstance(evidence_summary, dict) else []
        results.extend([
            check("response:observed:execution-status", execution.get("execution_status") == "observed"),
            check("response:observed:evidence-present", len(evidence_refs) >= 1, [str(evidence_refs)]),
            check("response:observed:receipt-present", isinstance(receipt_refs, list) and len(receipt_refs) >= 1, [str(receipt_refs)]),
            check("response:observed:no-warnings", data.get("warnings") == [], [str(data.get("warnings"))]),
        ])
    if status == "environment_failed":
        failure_codes = evidence_summary.get("failure_codes", []) if isinstance(evidence_summary, dict) else []
        results.extend([
            check("response:failed:execution-status", execution.get("execution_status") == "failed"),
            check("response:failed:evidence-present", len(evidence_refs) >= 1, [str(evidence_refs)]),
            check("response:failed:failure-code", "synthetic_validation_failed" in failure_codes, [str(failure_codes)]),
            check("response:failed:warning", "environment_validation_failed" in data.get("warnings", []), [str(data.get("warnings", []))]),
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
