#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "contracts/workspace/workroom-update-request.example.json"
RESPONSE = ROOT / "contracts/workspace/workroom-update-response.accepted.example.json"
INVALID_RESPONSES = [
    ROOT / "contracts/workspace/workroom-update-response.invalid-runtime-mutation.example.json",
]

REQUIRED_REQUEST_FIELDS = {
    "schemaVersion",
    "requestId",
    "workroomId",
    "requestedBy",
    "requestedAt",
    "operation",
    "workspaceContractRef",
    "workroomRef",
    "professionalWorkroomRef",
    "policyDecisionRefs",
    "privacyDecisionRefs",
    "topicPackRefs",
    "memoryScopeRefs",
    "audioReviewRefs",
    "learningReceiptRefs",
    "semanticReceiptRefs",
    "expectedEffect",
    "claimBoundary",
}
REQUIRED_RESPONSE_FIELDS = {
    "schemaVersion",
    "requestId",
    "workroomId",
    "status",
    "acceptedAt",
    "runtimeMutationPerformed",
    "evidenceRefs",
    "receiptRefs",
    "requiredNextGates",
    "claimBoundary",
}
REQUIRED_LIST_FIELDS = {
    "policyDecisionRefs",
    "privacyDecisionRefs",
    "topicPackRefs",
    "memoryScopeRefs",
    "audioReviewRefs",
    "learningReceiptRefs",
    "semanticReceiptRefs",
}
REQUEST_CLAIM_BOUNDARIES = {
    "This request fixture is a contract example only.",
    "It does not perform a live workroom update.",
    "It does not grant memory, learning, linking, or agent action authority.",
}
RESPONSE_CLAIM_BOUNDARIES = {
    "accepted_for_review is not runtime execution.",
    "No workroom state was mutated by this fixture.",
    "Runtime implementation requires a separate platform service contract and receipt path.",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def require_fields(data: dict[str, Any], required: set[str], label: str) -> list[str]:
    missing = sorted(required - set(data))
    if missing:
        return [f"{label} missing required fields: {missing}"]
    return []


def require_nonempty_string_list(data: dict[str, Any], field: str, label: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list) or not value:
        return [f"{label}.{field} must be a non-empty list"]
    if not all(isinstance(item, str) and item for item in value):
        return [f"{label}.{field} must contain only non-empty strings"]
    return []


def require_set_contains(value: Any, required: set[str], label: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    missing = sorted(required - set(value))
    if missing:
        return [f"{label} missing required values: {missing}"]
    return []


def validate_request(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(require_fields(request, REQUIRED_REQUEST_FIELDS, "request"))
    for field in REQUIRED_LIST_FIELDS:
        errors.extend(require_nonempty_string_list(request, field, "request"))
    if request.get("schemaVersion") != "v0.1":
        errors.append("request.schemaVersion must be v0.1")
    errors.extend(require_set_contains(request.get("claimBoundary", []), REQUEST_CLAIM_BOUNDARIES, "request.claimBoundary"))
    return errors


def validate_response(response: dict[str, Any], request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(require_fields(response, REQUIRED_RESPONSE_FIELDS, "response"))
    if response.get("schemaVersion") != "v0.1":
        errors.append("response.schemaVersion must be v0.1")
    if request.get("requestId") != response.get("requestId"):
        errors.append("response.requestId must match request.requestId")
    if request.get("workroomId") != response.get("workroomId"):
        errors.append("response.workroomId must match request.workroomId")
    if response.get("status") != "accepted_for_review":
        errors.append("response.status must be accepted_for_review")
    if response.get("runtimeMutationPerformed") is not False:
        errors.append("response.runtimeMutationPerformed must be false for this fixture")
    errors.extend(require_set_contains(response.get("claimBoundary", []), RESPONSE_CLAIM_BOUNDARIES, "response.claimBoundary"))
    errors.extend(require_nonempty_string_list(response, "evidenceRefs", "response"))
    errors.extend(require_nonempty_string_list(response, "receiptRefs", "response"))
    errors.extend(require_nonempty_string_list(response, "requiredNextGates", "response"))
    return errors


def main() -> int:
    try:
        request = load_json(REQUEST)
        response = load_json(RESPONSE)
    except ValueError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    if not isinstance(request, dict):
        errors.append("request fixture must be an object")
        request = {}
    if not isinstance(response, dict):
        errors.append("response fixture must be an object")
        response = {}

    errors.extend(validate_request(request))
    errors.extend(validate_response(response, request))

    for invalid_path in INVALID_RESPONSES:
        try:
            invalid_response = load_json(invalid_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(invalid_response, dict):
            print(f"OK: invalid fixture rejected: {invalid_path.relative_to(ROOT)}")
            continue
        invalid_errors = validate_response(invalid_response, request)
        if not invalid_errors:
            errors.append(f"invalid fixture unexpectedly passed: {invalid_path.relative_to(ROOT)}")
        else:
            print(f"OK: invalid fixture rejected: {invalid_path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERR: {error}", file=sys.stderr)
        return 2

    print("OK: workroom update request fixture valid")
    print("OK: workroom update response fixture valid")
    print("OK: no-runtime mutation boundary preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
