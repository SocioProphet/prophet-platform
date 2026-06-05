#!/usr/bin/env python3
"""Validate WorkspaceOperation PROPHET receipt-to-claim projection fixture."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTION = ROOT / "contracts" / "workspace-prophet" / "e2e" / "claim-projection-workspace-operation-prophet-v0.json"
RECEIPTS = ROOT / "contracts" / "workspace-prophet" / "e2e" / "action-receipt-workspace-operation-prophet-v0.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    projection = load_json(PROJECTION)
    receipts_pack = load_json(RECEIPTS)
    receipts = {item["receipt_id"]: item for item in receipts_pack.get("receipts", [])}

    claim = projection.get("claim") or {}
    thread = projection.get("evidence_thread") or {}
    source_receipt_id = projection.get("source_receipt_id")

    failures = []
    if source_receipt_id not in receipts:
        failures.append(f"source receipt not found: {source_receipt_id}")
    if source_receipt_id not in claim.get("receipt_ids", []):
        failures.append("claim.receipt_ids must include source receipt")
    if source_receipt_id not in claim.get("evidence_ids", []):
        failures.append("claim.evidence_ids must include source receipt")
    if claim.get("claim_type") != "observation":
        failures.append("claim_type must be observation for runtime evidence projection")
    if claim.get("status") != "supported":
        failures.append("claim.status must be supported")
    if thread.get("claim_id") != claim.get("claim_id"):
        failures.append("evidence_thread.claim_id must match claim.claim_id")

    evidence_ids = {item.get("evidence_id") for item in thread.get("evidence_items", [])}
    for expected in claim.get("evidence_ids", []):
        if expected not in evidence_ids:
            failures.append(f"thread missing claim evidence id: {expected}")
    for operation_id in claim.get("operation_ids", []):
        if operation_id not in evidence_ids:
            failures.append(f"thread missing operation evidence id: {operation_id}")
    for capability_id in claim.get("capability_ids", []):
        if capability_id not in evidence_ids:
            failures.append(f"thread missing capability evidence id: {capability_id}")

    if failures:
        print("Workspace PROPHET claim projection validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Workspace PROPHET claim projection validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
