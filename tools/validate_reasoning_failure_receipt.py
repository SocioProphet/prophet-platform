#!/usr/bin/env python3
"""Validate ReasoningFailureReceipt v0.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED = {
    "schemaVersion",
    "recordType",
    "receipt_id",
    "case_id",
    "case_type",
    "suite_id",
    "perturbation_ids",
    "data_boundary",
    "provider_dependency",
    "llm_judge_used",
    "deterministic_verifier_refs",
    "verifier_results",
    "invariant_outcomes",
    "policy_decision",
    "residual_risk",
    "mitigation_suggestions",
    "next_action",
    "evidence_refs",
    "downstream_refs",
    "issued_at",
    "receipt_hash",
}
POLICY_DECISIONS = {"allow", "warn", "require-review", "quarantine", "block", "rollback", "revoke"}
NEXT_ACTIONS = {"record-only", "require-review", "quarantine", "block", "open-issue"}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"{path}: expected JSON object")
    return payload


def require_string(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        fail(f"{key}: expected non-empty string")
    return value


def require_list(record: dict[str, Any], key: str, *, allow_empty: bool = False) -> list[Any]:
    value = record.get(key)
    if not isinstance(value, list):
        fail(f"{key}: expected list")
    if not allow_empty and not value:
        fail(f"{key}: expected non-empty list")
    return value


def validate_receipt(record: dict[str, Any]) -> None:
    missing = sorted(REQUIRED - set(record))
    if missing:
        fail(f"missing required fields: {missing}")
    if record["schemaVersion"] != "prophet-platform.reasoning-failure-receipt.v0.1":
        fail("schemaVersion mismatch")
    if record["recordType"] != "ReasoningFailureReceipt":
        fail("recordType mismatch")
    for key in ("receipt_id", "case_id", "case_type", "suite_id", "data_boundary", "provider_dependency", "policy_decision", "residual_risk", "next_action", "issued_at", "receipt_hash"):
        require_string(record, key)
    if record["data_boundary"] != "synthetic":
        fail("first reasoning-failure receipt slice must be synthetic")
    if record["provider_dependency"] != "none":
        fail("first reasoning-failure receipt slice must be provider-neutral")
    if record.get("llm_judge_used") is not False:
        fail("llm_judge_used must be false")
    if not record["receipt_hash"].startswith("sha256:"):
        fail("receipt_hash must be sha256-bound")
    if record["policy_decision"] not in POLICY_DECISIONS:
        fail("unknown policy_decision")
    if record["next_action"] not in NEXT_ACTIONS:
        fail("unknown next_action")
    require_list(record, "perturbation_ids")
    verifier_refs = require_list(record, "deterministic_verifier_refs")
    if any(not isinstance(ref, str) or not ref.startswith("verifier://") for ref in verifier_refs):
        fail("deterministic_verifier_refs must be verifier:// refs")
    validate_verifier_results(require_list(record, "verifier_results"))
    validate_invariant_outcomes(require_list(record, "invariant_outcomes"))
    evidence_refs = require_list(record, "evidence_refs")
    if any(not isinstance(ref, str) or not ref.startswith("evidence://") for ref in evidence_refs):
        fail("evidence_refs must be redacted evidence:// refs")
    require_list(record, "mitigation_suggestions", allow_empty=True)
    downstream = record.get("downstream_refs")
    if not isinstance(downstream, dict):
        fail("downstream_refs must be an object")
    for key in ("model_governance_ledger", "guardrail_fabric", "agentplane", "sherlock"):
        require_string(downstream, key)

    any_fail = any(result.get("status") != "pass" for result in record["verifier_results"])
    if any_fail and record["policy_decision"] == "allow":
        fail("failing deterministic verifier cannot allow")
    if any_fail and record["next_action"] == "record-only":
        fail("failing deterministic verifier cannot be record-only")


def validate_verifier_results(results: list[Any]) -> None:
    for result in results:
        if not isinstance(result, dict):
            fail("verifier_results entries must be objects")
        for key in ("verifier_ref", "verifier_kind", "status", "message"):
            require_string(result, key)
        if result["status"] not in {"pass", "fail", "warn"}:
            fail("unknown verifier result status")
        if not result["verifier_ref"].startswith("verifier://"):
            fail("verifier_ref must be verifier:// ref")
        if result["verifier_kind"] == "llm-judge":
            fail("LLM-only judge verifier is not allowed in first slice")


def validate_invariant_outcomes(outcomes: list[Any]) -> None:
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            fail("invariant_outcomes entries must be objects")
        for key in ("invariant", "status", "case_ref", "suite_ref"):
            require_string(outcome, key)
        if outcome["status"] not in {"pass", "fail", "warn"}:
            fail("unknown invariant outcome status")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_reasoning_failure_receipt.py <receipt.json>", file=sys.stderr)
        return 2
    try:
        validate_receipt(load_json(Path(argv[1])))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {argv[1]} validates as ReasoningFailureReceipt v0.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
