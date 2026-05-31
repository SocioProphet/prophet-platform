#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST = ROOT / "contracts/workspace/workroom-update-request.example.json"
DEFAULT_OUTPUT = ROOT / "build/workroom-update/workroom-update-receipt.example.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def require_list(request: dict[str, Any], field: str) -> list[str]:
    value = request.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"request.{field} must be a non-empty list")
    if not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"request.{field} must contain only non-empty strings")
    return value


def build_receipt(request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("requestId")
    workroom_id = request.get("workroomId")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request.requestId must be a non-empty string")
    if not isinstance(workroom_id, str) or not workroom_id:
        raise ValueError("request.workroomId must be a non-empty string")

    refs = {
        "policyDecisionRefs": require_list(request, "policyDecisionRefs"),
        "privacyDecisionRefs": require_list(request, "privacyDecisionRefs"),
        "topicPackRefs": require_list(request, "topicPackRefs"),
        "memoryScopeRefs": require_list(request, "memoryScopeRefs"),
        "audioReviewRefs": require_list(request, "audioReviewRefs"),
        "learningReceiptRefs": require_list(request, "learningReceiptRefs"),
        "semanticReceiptRefs": require_list(request, "semanticReceiptRefs"),
    }

    input_hash = sha256_hex(request)
    receipt = {
        "schemaVersion": "v0.1",
        "receiptId": f"workroom-update-receipt::{request_id}",
        "requestId": request_id,
        "workroomId": workroom_id,
        "status": "synthetic_receipt_emitted",
        "runtimeMutationPerformed": False,
        "operation": request.get("operation"),
        "workspaceContractRef": request.get("workspaceContractRef"),
        "professionalWorkroomRef": request.get("professionalWorkroomRef"),
        "inputHash": input_hash,
        "outputHash": "sha256:computed-after-canonicalization",
        "evidenceRefs": [
            f"evidence://platform/workroom-update/{request_id}/input-hash",
            f"evidence://platform/workroom-update/{request_id}/no-runtime-mutation",
        ],
        "policyDecisionRefs": refs["policyDecisionRefs"],
        "privacyDecisionRefs": refs["privacyDecisionRefs"],
        "topicPackRefs": refs["topicPackRefs"],
        "memoryScopeRefs": refs["memoryScopeRefs"],
        "audioReviewRefs": refs["audioReviewRefs"],
        "learningReceiptRefs": refs["learningReceiptRefs"],
        "semanticReceiptRefs": refs["semanticReceiptRefs"],
        "claimBoundary": [
            "This receipt is synthetic and local-build only.",
            "It proves contract receipt emission shape, not runtime execution.",
            "It does not mutate workroom state, write to a database, call an API, or grant memory/linking/action authority.",
        ],
    }
    output_hash = sha256_hex({**receipt, "outputHash": "sha256:computed-after-canonicalization"})
    receipt["outputHash"] = output_hash
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a synthetic workroom update receipt from a request fixture.")
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    request_path = args.request if args.request.is_absolute() else ROOT / args.request
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    request = load_json(request_path)
    receipt = build_receipt(request)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: emitted {output_path.relative_to(ROOT)}")
    print(f"OK: inputHash={receipt['inputHash']}")
    print(f"OK: outputHash={receipt['outputHash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
