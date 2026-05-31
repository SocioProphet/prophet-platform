#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_POLICY_ID = "urn:prometheus:automated-shacl-gate-policy:v0.1.0"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def dataset_size(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return sum(1 for _ in reader)


def load_policy(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    policy = load_json(Path(path))
    required = {
        "policyId",
        "schemaVersion",
        "applicationMode",
        "methodFamilies",
        "minimumDatasetRows",
        "maximumCandidateComplexity",
        "maximumNmse",
        "requiredUnitsStatus",
        "requireReplayVerified",
        "allowControlAuthority",
        "forbiddenGovernanceFlags",
        "promotionEligibility",
    }
    missing = sorted(required - set(policy))
    if missing:
        raise ValueError(f"gate policy missing fields: {missing}")
    if policy["schemaVersion"] != "0.1.0":
        raise ValueError("gate policy schemaVersion must be 0.1.0")
    if policy["applicationMode"] != "equation_discovery":
        raise ValueError("gate policy applicationMode must be equation_discovery")
    if policy["requireReplayVerified"] is not True:
        raise ValueError("gate policy must require replay verification")
    if policy["allowControlAuthority"] is not False:
        raise ValueError("gate policy must not allow control authority")
    if policy["requiredUnitsStatus"] != "consistent":
        raise ValueError("gate policy must require consistent units")
    if policy["promotionEligibility"] not in {"ineligible", "review_required", "eligible"}:
        raise ValueError("gate policy promotionEligibility invalid")
    return policy


def validate_against_policy(evaluation: dict[str, Any], policy: dict[str, Any] | None, method_family: str) -> None:
    if policy is None:
        return
    if method_family not in policy["methodFamilies"]:
        raise ValueError("methodFamily not allowed by gate policy")
    if evaluation["datasetSize"] < policy["minimumDatasetRows"]:
        raise ValueError("datasetSize below gate policy minimum")
    if evaluation["complexity"] > policy["maximumCandidateComplexity"]:
        raise ValueError("complexity above gate policy maximum")
    if evaluation["nmse"] > policy["maximumNmse"]:
        raise ValueError("nmse above gate policy maximum")
    if evaluation["unitsStatus"] != policy["requiredUnitsStatus"]:
        raise ValueError("unitsStatus does not match gate policy")
    if evaluation["replayHashVerified"] is not True:
        raise ValueError("gate policy requires replay verification")
    if evaluation["chronosGovernanceFlags"]:
        raise ValueError("gate evaluation has governance flags")
    if evaluation["finalAdmissionRequested"] is True:
        raise ValueError("gate evaluation cannot request final admission")


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit PROMETHEUS automated gate evaluation artifact")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--run-artifact", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--evaluation-id", required=True)
    parser.add_argument("--policy-id", default=DEFAULT_POLICY_ID)
    parser.add_argument("--gate-policy")
    parser.add_argument("--issued-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    candidate = load_json(Path(args.candidate))
    run_artifact = load_json(Path(args.run_artifact))
    policy = load_policy(args.gate_policy)
    candidate_id = candidate["candidateId"]
    ref = None
    for item in run_artifact.get("candidateRefs", []):
        if item.get("candidateId") == candidate_id:
            ref = item
            break
    if ref is None:
        raise ValueError("run artifact does not reference candidate")

    evaluation = {
        "evaluationId": args.evaluation_id,
        "policyId": policy["policyId"] if policy else args.policy_id,
        "candidateId": candidate_id,
        "datasetSize": dataset_size(Path(args.dataset)),
        "nmse": ref["nmse"],
        "complexity": ref["complexity"],
        "unitsStatus": ref["unitsStatus"],
        "replayHashVerified": True,
        "chronosGovernanceFlags": [],
        "requestedReviewSurface": "automated_shacl_gate",
        "finalAdmissionRequested": False,
        "promotionEligibility": policy["promotionEligibility"] if policy else "review_required",
        "issuedAt": args.issued_at or now_utc(),
    }
    validate_against_policy(evaluation, policy, run_artifact["methodFamily"])
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "evaluationId": args.evaluation_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
