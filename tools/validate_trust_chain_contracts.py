#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "contracts" / "trust-chain" / "admit-artifact-request.example.json",
    ROOT / "contracts" / "trust-chain" / "admit-artifact-response.allowed.example.json",
    ROOT / "contracts" / "trust-chain" / "admit-artifact-response.denied.example.json",
]

SCHEMA_VERSION = "0.1"
ARTIFACT_TYPES = {
    "SourceArtifact",
    "PackageArtifact",
    "RuntimeAsset",
    "BootReleaseSet",
    "ModelArtifact",
    "DatasetArtifact",
    "AgentArtifact",
    "ToolArtifact",
    "WorkflowArtifact",
}
DECISIONS = {"allow", "deny", "escalate", "quarantine", "allow_with_context", "provisional"}
REQUIRED_REQUEST_EVIDENCE = {
    "sbom_ref",
    "vex_ref",
    "lockfile_ref",
    "signature_ref",
    "scan_record_ref",
    "policy_profile_ref",
}
REQUIRED_POSTURE_KEYS = {
    "source_posture",
    "package_posture",
    "runtime_posture",
    "vulnerability_posture",
    "patch_posture",
    "policy_posture",
    "agentplane_posture",
    "promotion_posture",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture must be a JSON object: {path}")
    return data


def check(check_id: str, passed: bool, diagnostics: list[str] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "diagnostics": diagnostics or []}


def digest_is_valid(digest: Any) -> bool:
    return (
        isinstance(digest, dict)
        and digest.get("algorithm") in {"sha256", "sha512"}
        and isinstance(digest.get("value"), str)
        and len(digest.get("value", "")) >= 32
    )


def validate_scope(prefix: str, scope: Any) -> list[dict[str, Any]]:
    if not isinstance(scope, dict):
        return [check(f"{prefix}:scope-object", False, [str(scope)])]
    return [
        check(f"{prefix}:scope-environment", scope.get("environment") in {"local", "preview", "staging", "production"}, [str(scope.get("environment"))]),
        check(f"{prefix}:scope-tenant", str(scope.get("tenant_ref", "")).startswith("tenant://"), [str(scope.get("tenant_ref"))]),
        check(f"{prefix}:scope-workspace", str(scope.get("workspace_ref", "")).startswith("workspace://"), [str(scope.get("workspace_ref"))]),
        check(f"{prefix}:scope-risk-tier", scope.get("risk_tier") in {"internal", "enterprise", "regulated_enterprise"}, [str(scope.get("risk_tier"))]),
    ]


def validate_artifact(prefix: str, artifact: Any) -> list[dict[str, Any]]:
    if not isinstance(artifact, dict):
        return [check(f"{prefix}:artifact-object", False, [str(artifact)])]
    return [
        check(f"{prefix}:artifact-type", artifact.get("artifact_type") in ARTIFACT_TYPES, [str(artifact.get("artifact_type"))]),
        check(f"{prefix}:artifact-ref", "://" in str(artifact.get("artifact_ref", "")), [str(artifact.get("artifact_ref"))]),
        check(f"{prefix}:artifact-digest", digest_is_valid(artifact.get("digest")), [str(artifact.get("digest"))]),
    ]


def validate_request(data: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = data.get("evidence_refs", {})
    requested_checks = data.get("requested_checks", [])
    results = [
        check("request:schema-version", data.get("schema_version") == SCHEMA_VERSION, [str(data.get("schema_version"))]),
        check("request:id", str(data.get("request_id", "")).startswith("trust-chain:admit-artifact-request:"), [str(data.get("request_id"))]),
        check("request:decision-kind", data.get("requested_decision") in {"production_admission", "preview_admission", "runtime_validation"}, [str(data.get("requested_decision"))]),
        check("request:evidence-object", isinstance(evidence, dict) and bool(evidence), [str(evidence)]),
        check("request:required-evidence", REQUIRED_REQUEST_EVIDENCE.issubset(set(evidence.keys())) if isinstance(evidence, dict) else False, [str(sorted(evidence.keys())) if isinstance(evidence, dict) else str(evidence)]),
        check("request:requested-checks", isinstance(requested_checks, list) and len(requested_checks) >= 5, [str(requested_checks)]),
        check("request:non-claims", isinstance(data.get("non_claims"), list) and len(data.get("non_claims", [])) >= 1, [str(data.get("non_claims"))]),
    ]
    results.extend(validate_scope("request", data.get("requested_scope")))
    results.extend(validate_artifact("request", data.get("artifact")))
    return results


def validate_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    decision = data.get("decision")
    posture = data.get("posture", {})
    evidence_refs = data.get("evidence_refs", [])
    remediation = data.get("remediation", [])
    warnings = data.get("warnings", [])
    results = [
        check(f"response:{decision}:schema-version", data.get("schema_version") == SCHEMA_VERSION, [str(data.get("schema_version"))]),
        check(f"response:{decision}:request-id", str(data.get("request_id", "")).startswith("trust-chain:admit-artifact-request:"), [str(data.get("request_id"))]),
        check(f"response:{decision}:response-id", str(data.get("response_id", "")).startswith("trust-chain:admit-artifact-response:"), [str(data.get("response_id"))]),
        check(f"response:{decision}:status", data.get("status") == "admission_decided", [str(data.get("status"))]),
        check(f"response:{decision}:decision", decision in DECISIONS, [str(decision)]),
        check(f"response:{decision}:posture-object", isinstance(posture, dict) and bool(posture), [str(posture)]),
        check(f"response:{decision}:required-posture", REQUIRED_POSTURE_KEYS.issubset(set(posture.keys())) if isinstance(posture, dict) else False, [str(sorted(posture.keys())) if isinstance(posture, dict) else str(posture)]),
        check(f"response:{decision}:evidence-refs", isinstance(evidence_refs, list) and len(evidence_refs) >= 1, [str(evidence_refs)]),
        check(f"response:{decision}:warnings-list", isinstance(warnings, list), [str(warnings)]),
        check(f"response:{decision}:non-claims", isinstance(data.get("non_claims"), list) and len(data.get("non_claims", [])) >= 1, [str(data.get("non_claims"))]),
    ]
    results.extend(validate_scope(f"response:{decision}", data.get("decision_scope")))
    results.extend(validate_artifact(f"response:{decision}", data.get("artifact")))

    if decision == "allow":
        results.extend([
            check("response:allow:no-remediation", remediation == [], [str(remediation)]),
            check("response:allow:no-warnings", warnings == [], [str(warnings)]),
            check("response:allow:policy-satisfied", posture.get("policy_posture") == "satisfied" if isinstance(posture, dict) else False, [str(posture.get("policy_posture")) if isinstance(posture, dict) else str(posture)]),
            check("response:allow:agentplane-validated", posture.get("agentplane_posture") == "validated" if isinstance(posture, dict) else False, [str(posture.get("agentplane_posture")) if isinstance(posture, dict) else str(posture)]),
        ])
    if decision in {"deny", "quarantine"}:
        results.extend([
            check(f"response:{decision}:remediation-required", isinstance(remediation, list) and len(remediation) >= 2, [str(remediation)]),
            check(f"response:{decision}:warnings-present", isinstance(warnings, list) and len(warnings) >= 1, [str(warnings)]),
            check(f"response:{decision}:policy-not-satisfied", posture.get("policy_posture") in {"failed", "blocked"} if isinstance(posture, dict) else False, [str(posture.get("policy_posture")) if isinstance(posture, dict) else str(posture)]),
            check(
                f"response:{decision}:required-remediation-authority",
                all(isinstance(item, dict) and item.get("required_before_admission") is True and bool(item.get("authority")) for item in remediation),
                [str(remediation)],
            ),
        ])
    return results


def main() -> int:
    results: list[dict[str, Any]] = []
    for path in FIXTURES:
        data = load(path)
        if "requested_decision" in data:
            results.extend(validate_request(data))
        else:
            results.extend(validate_response(data))
    passed = all(item["passed"] for item in results)
    print(json.dumps({"validator": "prophet-platform.trust-chain.contracts.v0.1", "passed": passed, "results": results}, indent=2, sort_keys=True))
    print(("PASS" if passed else "FAIL") + ": trust-chain admission fixtures")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
