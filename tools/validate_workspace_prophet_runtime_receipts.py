#!/usr/bin/env python3
"""Validate generated WorkspaceOperation + PROPHET runtime receipt fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "build" / "workspace-prophet" / "runtime-receipts.generated.json"
EMITTER = ROOT / "tools" / "emit_workspace_prophet_runtime_receipts.py"
REQUIRED_RESULTS = {
    "op_readonly_diagnostics_demo": "completed",
    "op_readonly_diagnostics_missing_capability_demo": "blocked",
    "op_readonly_diagnostics_expired_capability_demo": "blocked",
}
REQUIRED_REASON_BY_OPERATION = {
    "op_readonly_diagnostics_demo": "scoped_capability_valid",
    "op_readonly_diagnostics_missing_capability_demo": "missing_scoped_capability",
    "op_readonly_diagnostics_expired_capability_demo": "expired_scoped_capability",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    subprocess.run([sys.executable, str(EMITTER), "--output", str(RECEIPTS)], check=True)
    payload = load_json(RECEIPTS)
    if payload.get("production_ready") is not False:
        print("runtime receipt pack must not claim production readiness")
        return 1

    receipts = {receipt.get("operation_id"): receipt for receipt in payload.get("receipts", [])}
    missing_ops = sorted(set(REQUIRED_RESULTS) - set(receipts))
    if missing_ops:
        print(f"missing runtime receipts for operations: {missing_ops}")
        return 1

    for operation_id, expected_result in REQUIRED_RESULTS.items():
        receipt = receipts[operation_id]
        if receipt.get("result_state") != expected_result:
            print(f"{operation_id}: expected {expected_result}, got {receipt.get('result_state')}")
            return 1
        expected_reason = REQUIRED_REASON_BY_OPERATION[operation_id]
        if expected_reason not in receipt.get("reason_codes", []):
            print(f"{operation_id}: missing reason code {expected_reason}")
            return 1
        if receipt.get("metadata", {}).get("production_ready") is not False:
            print(f"{operation_id}: receipt metadata must keep production_ready false")
            return 1
        if not receipt.get("receipt_hash", "").startswith("sha256:"):
            print(f"{operation_id}: receipt_hash must be sha256-prefixed")
            return 1

    print("Workspace PROPHET runtime receipts validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
