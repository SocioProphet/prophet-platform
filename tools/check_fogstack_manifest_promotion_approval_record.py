#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Fog Stack manifest promotion approval record")
    parser.add_argument("--approval-record", required=True, type=Path)
    parser.add_argument("--promotion-set", required=True, type=Path)
    parser.add_argument("--require-signed", action="store_true")
    args = parser.parse_args()

    record = load_json(args.approval_record)
    errors: list[str] = []

    if record.get("kind") != "FogStackManifestPromotionApprovalRecord":
        errors.append("approval record kind mismatch")
    if record.get("status") != "approved":
        errors.append(f"approval record status is not approved: {record.get('status')!r}")

    expected_digest = sha256_file(args.promotion_set)
    if record.get("promotion_set_digest") != expected_digest:
        errors.append("promotion set digest mismatch")

    required = record.get("required_approvals")
    approvals = record.get("approvals") or []
    if not isinstance(required, int) or required < 1:
        errors.append("required_approvals must be a positive integer")
    if not isinstance(approvals, list) or len(approvals) < (required if isinstance(required, int) else 1):
        errors.append("insufficient approvals")

    approvers: set[str] = set()
    for approval in approvals if isinstance(approvals, list) else []:
        if not isinstance(approval, dict):
            errors.append("approval entry is not an object")
            continue
        approver = approval.get("approver")
        role = approval.get("role")
        if not isinstance(approver, str) or not approver.strip():
            errors.append("approval entry missing approver")
        if not isinstance(role, str) or not role.strip():
            errors.append("approval entry missing role")
        if isinstance(approver, str):
            if approver in approvers:
                errors.append(f"duplicate approver: {approver}")
            approvers.add(approver)

    signed = record.get("signed")
    signature = record.get("signature")
    if args.require_signed:
        if signed is not True:
            errors.append("approval record is not marked signed")
        if not isinstance(signature, dict):
            errors.append("signed approval missing signature object")
        else:
            if signature.get("type") not in {"cosign", "sigstore", "other"}:
                errors.append("invalid signature type")
            if not isinstance(signature.get("ref"), str) or not signature.get("ref"):
                errors.append("signature ref missing")

    if errors:
        for item in errors:
            print(item)
        raise SystemExit(1)

    print("FogStack manifest promotion approval record passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
