#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "build/workroom-update/workroom-update-receipt.example.json"

REQUIRED_FIELDS = {
    "schemaVersion",
    "receiptId",
    "requestId",
    "workroomId",
    "status",
    "runtimeMutationPerformed",
    "operation",
    "workspaceContractRef",
    "professionalWorkroomRef",
    "inputHash",
    "outputHash",
    "evidenceRefs",
    "policyDecisionRefs",
    "privacyDecisionRefs",
    "topicPackRefs",
    "memoryScopeRefs",
    "audioReviewRefs",
    "learningReceiptRefs",
    "semanticReceiptRefs",
    "claimBoundary",
}
REQUIRED_LIST_FIELDS = {
    "evidenceRefs",
    "policyDecisionRefs",
    "privacyDecisionRefs",
    "topicPackRefs",
    "memoryScopeRefs",
    "audioReviewRefs",
    "learningReceiptRefs",
    "semanticReceiptRefs",
}
REQUIRED_BOUNDARIES = {
    "This receipt is synthetic and local-build only.",
    "It proves contract receipt emission shape, not runtime execution.",
    "It does not mutate workroom state, write to a database, call an API, or grant memory/linking/action authority.",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing {path.relative_to(ROOT)}; run tools/emit_workroom_update_receipt.py first")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return data


def require_nonempty_string_list(data: dict[str, Any], field: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list) or not value:
        return [f"receipt.{field} must be a non-empty list"]
    if not all(isinstance(item, str) and item for item in value):
        return [f"receipt.{field} must contain only non-empty strings"]
    return []


def main() -> int:
    try:
        receipt = load_json(RECEIPT)
    except ValueError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(receipt))
    if missing:
        errors.append(f"receipt missing required fields: {missing}")

    if receipt.get("schemaVersion") != "v0.1":
        errors.append("receipt.schemaVersion must be v0.1")
    if receipt.get("status") != "synthetic_receipt_emitted":
        errors.append("receipt.status must be synthetic_receipt_emitted")
    if receipt.get("runtimeMutationPerformed") is not False:
        errors.append("receipt.runtimeMutationPerformed must be false")
    if not str(receipt.get("inputHash", "")).startswith("sha256:"):
        errors.append("receipt.inputHash must use sha256: prefix")
    if not str(receipt.get("outputHash", "")).startswith("sha256:"):
        errors.append("receipt.outputHash must use sha256: prefix")

    for field in REQUIRED_LIST_FIELDS:
        errors.extend(require_nonempty_string_list(receipt, field))

    claim_boundary = receipt.get("claimBoundary")
    if not isinstance(claim_boundary, list):
        errors.append("receipt.claimBoundary must be a list")
    else:
        missing_boundaries = sorted(REQUIRED_BOUNDARIES - set(claim_boundary))
        if missing_boundaries:
            errors.append(f"receipt.claimBoundary missing required values: {missing_boundaries}")

    if errors:
        for error in errors:
            print(f"ERR: {error}", file=sys.stderr)
        return 2

    print("OK: synthetic workroom update receipt valid")
    print("OK: no-runtime mutation boundary preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
