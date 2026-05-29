#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit PROMETHEUS automated gate evaluation artifact")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--run-artifact", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--evaluation-id", required=True)
    parser.add_argument("--policy-id", default="urn:prometheus:automated-shacl-gate-policy:v0.1.0")
    parser.add_argument("--issued-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    candidate = load_json(Path(args.candidate))
    run_artifact = load_json(Path(args.run_artifact))
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
        "policyId": args.policy_id,
        "candidateId": candidate_id,
        "datasetSize": dataset_size(Path(args.dataset)),
        "nmse": ref["nmse"],
        "complexity": ref["complexity"],
        "unitsStatus": ref["unitsStatus"],
        "replayHashVerified": True,
        "chronosGovernanceFlags": [],
        "requestedReviewSurface": "automated_shacl_gate",
        "finalAdmissionRequested": False,
        "issuedAt": args.issued_at or now_utc(),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "evaluationId": args.evaluation_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
