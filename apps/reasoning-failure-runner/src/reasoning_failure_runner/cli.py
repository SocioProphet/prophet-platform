#!/usr/bin/env python3
"""Synthetic reasoning-failure runner.

This runner performs deterministic checks over synthetic cases and emits a
provider-neutral reasoning-failure receipt. It intentionally avoids LLM-as-judge
and keeps downstream ledger/guardrail/AgentPlane consumption separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "prophet-platform.reasoning-failure-receipt.v0.1"
RECORD_TYPE = "ReasoningFailureReceipt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def stable_hash(record: dict[str, Any]) -> str:
    copy = dict(record)
    copy.pop("receipt_hash", None)
    encoded = json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def verify_exact_string(case: dict[str, Any]) -> dict[str, Any]:
    expected = case.get("expected", {}).get("exactString")
    candidate = case.get("candidateOutput")
    passed = isinstance(expected, str) and candidate == expected
    return {
        "verifier_ref": "verifier://reasoning-failure/exact-string-v0.1",
        "verifier_kind": "deterministic-exact-string",
        "status": "pass" if passed else "fail",
        "expected_ref": "case.expected.exactString",
        "observed_ref": "case.candidateOutput",
        "message": "candidate output exactly matched expected string" if passed else "candidate output did not exactly match expected string",
    }


def run_case(case: dict[str, Any], suite: dict[str, Any], *, generated_at: str | None) -> dict[str, Any]:
    case_id = str(case.get("caseId", "reasoning-failure-case:unknown"))
    suite_id = str(suite.get("suiteId", "perturbation-suite:unknown"))
    case_type = str(case.get("caseType", "unknown"))
    if case.get("dataBoundary") != "synthetic":
        raise ValueError("first reasoning-failure slice requires synthetic dataBoundary")
    if case_type != "exact-string":
        raise ValueError(f"unsupported caseType for first slice: {case_type}")

    verifier = verify_exact_string(case)
    verifier_status = verifier["status"]
    failed = verifier_status != "pass"
    perturbations = suite.get("perturbations", [])
    if not isinstance(perturbations, list) or not perturbations:
        raise ValueError("suite.perturbations must be a non-empty array")

    receipt: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "recordType": RECORD_TYPE,
        "receipt_id": f"reasoning-failure-receipt:{case_id.split(':')[-1]}",
        "case_id": case_id,
        "case_type": case_type,
        "suite_id": suite_id,
        "perturbation_ids": [str(item.get("perturbationId", "missing")) for item in perturbations],
        "data_boundary": "synthetic",
        "provider_dependency": "none",
        "llm_judge_used": False,
        "deterministic_verifier_refs": [verifier["verifier_ref"]],
        "verifier_results": [verifier],
        "invariant_outcomes": [
            {
                "invariant": "exactString",
                "status": verifier_status,
                "case_ref": case_id,
                "suite_ref": suite_id,
            }
        ],
        "policy_decision": "block" if failed else "allow",
        "residual_risk": "medium" if failed else "low",
        "mitigation_suggestions": [
            "route exact-string tasks through deterministic post-check before completion"
        ] if failed else [],
        "next_action": "require-review" if failed else "record-only",
        "evidence_refs": list(case.get("evidenceRefs", [])),
        "downstream_refs": {
            "model_governance_ledger": "follow-up:model-governance-ledger/trustops-receipt-ledger-record",
            "guardrail_fabric": "follow-up:guardrail-fabric/trustops-guardrail-action-decision",
            "agentplane": "follow-up:agentplane/admission-consumption",
            "sherlock": "follow-up:sherlock/index-reasoning-failure-evidence",
        },
        "issued_at": generated_at or utc_now(),
        "labels": {"issue": "SocioProphet/prophet-platform#405", "source": "reasoning-failure-runner"},
    }
    receipt["receipt_hash"] = stable_hash(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reasoning-failure-runner")
    parser.add_argument("run", choices=["run"])
    parser.add_argument("--case", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        case = load_json(Path(args.case))
        suite = load_json(Path(args.suite))
        receipt = run_case(case, suite, generated_at=args.generated_at)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
