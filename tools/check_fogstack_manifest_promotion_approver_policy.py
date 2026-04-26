#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Fog Stack promotion approval roles")
    parser.add_argument("--approval-record", required=True, type=Path)
    parser.add_argument("--approver-policy", required=True, type=Path)
    args = parser.parse_args()

    record = load_json(args.approval_record)
    policy = yaml.safe_load(args.approver_policy.read_text(encoding="utf-8")) or {}

    approver_roles = {}
    for item in policy.get("approvers") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            approver_roles[item["id"]] = set(item.get("roles") or [])

    required_roles = set(policy.get("required_roles") or [])
    seen_roles = set()
    errors = []

    for approval in record.get("approvals") or []:
        approver = approval.get("approver") if isinstance(approval, dict) else None
        role = approval.get("role") if isinstance(approval, dict) else None
        if approver not in approver_roles:
            errors.append(f"unknown approver: {approver}")
            continue
        if role not in approver_roles[approver]:
            errors.append(f"role mismatch for approver: {approver}")
            continue
        seen_roles.add(role)

    missing = sorted(required_roles - seen_roles)
    if missing:
        errors.append("missing required roles: " + ", ".join(missing))

    if errors:
        for error in errors:
            print(error)
        return 1

    print("FogStack promotion approver policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
