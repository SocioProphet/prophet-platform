#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

RUNNER_ID = "prophet.reasoning-failure.exactness-runner"
RUNNER_VERSION = "0.1"

NEXT_CONSUMERS = [
    "SocioProphet/agentplane",
    "SocioProphet/guardrail-fabric",
    "SocioProphet/policy-fabric",
    "SocioProphet/model-governance-ledger",
    "SocioProphet/agent-registry",
    "SocioProphet/model-router",
    "SocioProphet/sherlock-search",
    "SocioProphet/delivery-excellence",
]


class ReasoningFailureRunnerError(ValueError):
    """Raised when a reasoning-failure fixture cannot be evaluated."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def emit_receipt(case: dict[str, Any], suite: dict[str, Any]) -> dict[str, Any]:
    _require_case(case)
    _require_suite(suite)
    if suite["targetCaseId"] != case["caseId"]:
        raise ReasoningFailureRunnerError("suite.targetCaseId must match case.caseId")
    if case["verifier"].get("llmJudgeOnly") is True:
        raise ReasoningFailureRunnerError("deterministic runner refuses LLM-judge-only cases")
    if case["privacyBoundary"] != "synthetic-only":
        raise ReasoningFailureRunnerError("v0.1 runner only admits synthetic-only fixtures")

    protected = case["protectedString"]
    observed = case["observedString"]
    passed = protected == observed
    decision = "passed" if passed else "failed"
    risk_action = "record-only" if passed else case["riskAction"]
    detail = "byte-identical" if passed else "byte mismatch"

    invariant_result = {
        "invariantId": case["invariant"]["invariantId"],
        "passed": passed,
        "expected": protected,
        "observed": observed,
        "detail": detail,
    }

    receipt_basis = {
        "caseId": case["caseId"],
        "suiteId": suite["suiteId"],
        "protectedString": protected,
        "observedString": observed,
        "passed": passed,
    }
    digest = hashlib.sha256(json.dumps(receipt_basis, sort_keys=True).encode("utf-8")).hexdigest()

    return {
        "kind": "ReasoningFailureReceipt",
        "version": "0.1",
        "receiptId": f"receipt:reasoning-failure:{digest[:24]}",
        "caseId": case["caseId"],
        "suiteId": suite["suiteId"],
        "runner": {
            "runnerId": RUNNER_ID,
            "runnerVersion": RUNNER_VERSION,
            "deterministic": True,
        },
        "privacyBoundary": case["privacyBoundary"],
        "failureModeRefs": case["failureModeRefs"],
        "verifierFamily": case["verifier"]["verifierFamily"],
        "invariantResults": [invariant_result],
        "decision": decision,
        "riskAction": risk_action,
        "evidenceRefs": list(dict.fromkeys(case["evidenceReceiptRefs"] + [f"evidence:byte-compare:{digest}"])),
        "mitigationRefs": case["mitigationRefs"],
        "residualRisk": case["residualRisk"],
        "nextConsumers": NEXT_CONSUMERS,
    }


def emit_receipt_from_paths(case_path: Path, suite_path: Path) -> dict[str, Any]:
    return emit_receipt(load_json(case_path), load_json(suite_path))


def _require_case(case: dict[str, Any]) -> None:
    required = [
        "kind",
        "version",
        "caseId",
        "failureModeRefs",
        "invariant",
        "protectedString",
        "observedString",
        "verifier",
        "evidenceReceiptRefs",
        "mitigationRefs",
        "residualRisk",
        "riskAction",
        "privacyBoundary",
    ]
    missing = [key for key in required if key not in case]
    if missing:
        raise ReasoningFailureRunnerError(f"case missing required keys: {missing}")
    if case["kind"] != "ReasoningFailureCase":
        raise ReasoningFailureRunnerError("case.kind must be ReasoningFailureCase")
    if not isinstance(case["protectedString"], str) or not isinstance(case["observedString"], str):
        raise ReasoningFailureRunnerError("protectedString and observedString must be strings")
    if case["verifier"].get("verifierFamily") != "deterministic":
        raise ReasoningFailureRunnerError("v0.1 exactness runner requires deterministic verifier family")


def _require_suite(suite: dict[str, Any]) -> None:
    required = ["kind", "version", "suiteId", "targetCaseId", "verifierFamily", "perturbations"]
    missing = [key for key in required if key not in suite]
    if missing:
        raise ReasoningFailureRunnerError(f"suite missing required keys: {missing}")
    if suite["kind"] != "ReasoningPerturbationSuite":
        raise ReasoningFailureRunnerError("suite.kind must be ReasoningPerturbationSuite")
    if suite["verifierFamily"] != "deterministic":
        raise ReasoningFailureRunnerError("v0.1 exactness runner requires deterministic suite verifier")
    if not suite["perturbations"]:
        raise ReasoningFailureRunnerError("suite must include at least one perturbation")


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a deterministic reasoning-failure receipt.")
    parser.add_argument("--case", required=True, type=Path, help="Path to ReasoningFailureCase JSON")
    parser.add_argument("--suite", required=True, type=Path, help="Path to ReasoningPerturbationSuite JSON")
    parser.add_argument("--out", required=True, type=Path, help="Output receipt path")
    args = parser.parse_args()

    receipt = emit_receipt_from_paths(args.case, args.suite)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
