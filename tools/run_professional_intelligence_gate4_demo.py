#!/usr/bin/env python3
"""Verify the Professional Intelligence OS Gate 4 demo orchestration.

This is a record-only runner. It does not call external services. It loads the
Gate 4 orchestration fixture, verifies the required end-to-end references and
steps, and emits a deterministic demo verification report for DelEx acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORCHESTRATION = ROOT / "contracts/orchestration/pi-gate4-demo.v0.1.example.json"
DEFAULT_OUTPUT = ROOT / "build/professional-intelligence/gate4-demo-verification.json"
REQUIRED_STEP_IDS = [
    "load-playbook",
    "resolve-context",
    "check-policy-and-obligations",
    "select-route-and-controls",
    "run-agentplane-bundle",
    "seal-ledger-and-adoption",
]
REQUIRED_REF_FIELDS = [
    "workroomRef",
    "playbookRef",
    "contextQueryRef",
    "contextPackRefs",
    "searchPacketRefs",
    "policyDecisionRefs",
    "obligationRefs",
    "routeDecisionRefs",
    "runtimeControlRefs",
    "agentAuthorityRefs",
    "agentplaneRunRefs",
    "ledgerRefs",
    "evidenceRefs",
    "adoptionEventRefs",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing orchestration file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


def ref_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value:
        return 1
    return 0


def verify(orchestration: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    failures: list[str] = []

    if orchestration.get("gate") != "gate-4":
        failures.append("gate must be gate-4")
    if orchestration.get("status") not in {"ready", "executed", "accepted"}:
        failures.append("status must be ready, executed, or accepted for demo verification")

    ref_summary = {field: ref_count(orchestration.get(field)) for field in REQUIRED_REF_FIELDS}
    for field, count in ref_summary.items():
        if count == 0:
            failures.append(f"{field} must not be empty")

    steps = orchestration.get("steps", [])
    step_ids = [step.get("stepId") for step in steps if isinstance(step, dict)]
    missing_steps = [step_id for step_id in REQUIRED_STEP_IDS if step_id not in step_ids]
    if missing_steps:
        failures.append(f"missing required steps: {missing_steps}")

    step_summaries = []
    for step in steps:
        if not isinstance(step, dict):
            failures.append("all steps must be objects")
            continue
        step_id = step.get("stepId", "<missing>")
        inputs = step.get("inputRefs", [])
        outputs = step.get("outputRefs", [])
        if step.get("evidenceRequired") is not True:
            failures.append(f"step {step_id} must require evidence")
        if not inputs:
            failures.append(f"step {step_id} must include inputRefs")
        if not outputs:
            failures.append(f"step {step_id} must include outputRefs")
        if step.get("status") not in {"ready", "executed", "accepted"}:
            failures.append(f"step {step_id} must be ready, executed, or accepted")
        step_summaries.append(
            {
                "stepId": step_id,
                "inputRefCount": len(inputs) if isinstance(inputs, list) else 0,
                "outputRefCount": len(outputs) if isinstance(outputs, list) else 0,
                "evidenceRequired": step.get("evidenceRequired") is True,
                "status": step.get("status"),
            }
        )

    acceptance = orchestration.get("acceptance", {})
    required_evidence = acceptance.get("requiredEvidenceRefs", [])
    required_adoption = acceptance.get("requiredAdoptionEventRefs", [])
    criteria = acceptance.get("criteria", [])
    if not required_evidence:
        failures.append("acceptance.requiredEvidenceRefs must not be empty")
    if not required_adoption:
        failures.append("acceptance.requiredAdoptionEventRefs must not be empty")
    if len(criteria) < 5:
        failures.append("acceptance.criteria must include at least five criteria")

    summary = {
        "demoId": orchestration.get("demoId"),
        "gate": orchestration.get("gate"),
        "status": orchestration.get("status"),
        "referenceSummary": ref_summary,
        "steps": step_summaries,
        "acceptance": {
            "requiredEvidenceCount": len(required_evidence) if isinstance(required_evidence, list) else 0,
            "requiredAdoptionEventCount": len(required_adoption) if isinstance(required_adoption, list) else 0,
            "criteriaCount": len(criteria) if isinstance(criteria, list) else 0,
        },
    }
    return not failures, failures, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orchestration", type=Path, default=DEFAULT_ORCHESTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    orchestration = load_json(args.orchestration)
    passed, failures, summary = verify(orchestration)
    report = {
        "schemaVersion": "v0.1",
        "kind": "ProfessionalIntelligenceGate4DemoVerification",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "orchestrationRef": str(args.orchestration.relative_to(ROOT) if args.orchestration.is_absolute() else args.orchestration),
        "passed": passed,
        "failures": failures,
        "summary": summary,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if passed:
        print(f"OK: Gate 4 demo verification passed; wrote {args.output}")
        return 0

    print(f"ERR: Gate 4 demo verification failed; wrote {args.output}", file=sys.stderr)
    for failure in failures:
        print(f" - {failure}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
