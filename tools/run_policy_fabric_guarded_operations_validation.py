#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUEST_CLIENT = ROOT / "tools" / "request_policy_fabric_operations_decision.py"
VALIDATOR = ROOT / "tools" / "validate_prophet_operations_policy_decisions.py"


class GuardedWorkflowError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GuardedWorkflowError(f"expected JSON object in {path}")
    return data


def first_policy_gated_recommendation(bundle: dict[str, Any]) -> dict[str, Any]:
    for recommendation in bundle.get("recommendations", []):
        if recommendation.get("policy_gate", {}).get("required") is True:
            return recommendation
    raise GuardedWorkflowError("bundle contains no policy-gated recommendation")


def run_checked(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise GuardedWorkflowError(
            "command failed with exit code "
            + str(result.returncode)
            + "\nCOMMAND: "
            + " ".join(cmd)
            + "\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a Policy Fabric operation decision and validate an operations bundle without executing remediation")
    parser.add_argument("--endpoint", required=True, help="Policy Fabric base URL")
    parser.add_argument("--bundle", type=Path, required=True, help="ProphetOperationsEvidenceBundle JSON")
    parser.add_argument("--mode", default="report_only", choices=["report_only", "enforcing"])
    parser.add_argument("--workdir", type=Path, required=True, help="Directory for generated decision/report artifacts")
    parser.add_argument("--require-executable", action="store_true", help="Fail unless fetched decision allows execution")
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    recommendation = first_policy_gated_recommendation(bundle)
    args.workdir.mkdir(parents=True, exist_ok=True)
    recommendation_path = args.workdir / "policy_fabric_recommendation.json"
    decision_path = args.workdir / "policy_fabric_decision.json"
    report_path = args.workdir / "policy_fabric_validation_report.json"
    recommendation_path.write_text(json.dumps(recommendation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    run_checked(
        [
            sys.executable,
            str(REQUEST_CLIENT),
            "--endpoint",
            args.endpoint,
            "--recommendation",
            str(recommendation_path),
            "--mode",
            args.mode,
            "--output",
            str(decision_path),
        ]
    )
    validator_cmd = [
        sys.executable,
        str(VALIDATOR),
        "--bundle",
        str(args.bundle),
        "--decision",
        str(decision_path),
        "--output",
        str(report_path),
    ]
    if args.require_executable:
        validator_cmd.append("--require-executable")
    run_checked(validator_cmd)

    report = load_json(report_path)
    result = {
        "ok": True,
        "executed_remediation": False,
        "mode": args.mode,
        "recommendation_path": str(recommendation_path),
        "decision_path": str(decision_path),
        "report_path": str(report_path),
        "summary": report.get("summary", {}),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
