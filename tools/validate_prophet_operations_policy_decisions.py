#!/usr/bin/env python3
"""Validate Prophet operations recommendations against Policy Fabric action decisions.

This validator enforces the first non-execution safety boundary for Prophet operations
intelligence:

- recommendations that require policy decisions must resolve to a matching decision artifact;
- decision artifacts must validate against the vendored Policy Fabric
  `ProphetOperationsActionDecision` JSON Schema;
- pending, deny, manual_review, defer, and unknown decisions are blocked for execution;
- allow decisions are only executable when recommendation/action/subject linkage is consistent.

The validator intentionally performs local checks. It does not call a live Policy Fabric service and
it does not execute remediation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
POLICY_FABRIC_DECISION_SCHEMA = ROOT / "schemas" / "external" / "policy-fabric" / "prophet_operations_action_decision_v1.schema.json"

ALLOWED_EXECUTION_OUTCOME = "allow"
BLOCKING_OUTCOMES = {"pending", "deny", "manual_review", "defer", "unknown"}
EXPECTED_DECISION_KIND = "ProphetOperationsActionDecision"
EXPECTED_DECISION_VERSION = "v1"
EXPECTED_RECOMMENDATION_KIND = "ProphetOptimizationRecommendation"
EXPECTED_BUNDLE_KIND = "ProphetOperationsEvidenceBundle"


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy_fabric_schema() -> Dict[str, Any]:
    if not POLICY_FABRIC_DECISION_SCHEMA.exists():
        raise ValidationError(f"missing vendored Policy Fabric schema: {POLICY_FABRIC_DECISION_SCHEMA}")
    return load_json(POLICY_FABRIC_DECISION_SCHEMA)


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def validate_decision_schema(decision: Dict[str, Any], schema: Dict[str, Any]) -> None:
    try:
        jsonschema.validate(decision, schema)
    except jsonschema.ValidationError as exc:
        decision_id = decision.get("decision_id", "<unknown>")
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise ValidationError(f"decision {decision_id} failed Policy Fabric schema validation at {path}: {exc.message}") from exc


def decision_index(decisions: Iterable[Dict[str, Any]], schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for decision in decisions:
        validate_decision_schema(decision, schema)
        if decision.get("kind") != EXPECTED_DECISION_KIND:
            raise ValidationError(f"decision has invalid kind: {decision.get('kind')}")
        if decision.get("schema_version") != EXPECTED_DECISION_VERSION:
            raise ValidationError(f"decision {decision.get('decision_id')} has invalid schema_version: {decision.get('schema_version')}")
        ref = decision.get("recommendation_ref")
        if not ref:
            raise ValidationError(f"decision {decision.get('decision_id')} is missing recommendation_ref")
        if ref in index:
            raise ValidationError(f"duplicate decision for recommendation_ref={ref}")
        index[ref] = decision
    return index


def validate_decision_link(recommendation: Dict[str, Any], decision: Dict[str, Any]) -> Tuple[bool, str]:
    rec_id = recommendation.get("recommendation_id")
    if recommendation.get("kind") != EXPECTED_RECOMMENDATION_KIND:
        raise ValidationError(f"recommendation {rec_id} has invalid kind: {recommendation.get('kind')}")
    if decision.get("recommendation_ref") != rec_id:
        raise ValidationError(f"decision {decision.get('decision_id')} does not reference recommendation {rec_id}")

    rec_subject = recommendation.get("subject", {})
    dec_subject = decision.get("subject", {})
    for field in ("id", "type"):
        if dec_subject.get(field) is not None and dec_subject.get(field) != rec_subject.get(field):
            raise ValidationError(
                f"decision {decision.get('decision_id')} subject.{field}={dec_subject.get(field)!r} does not match recommendation {rec_id} subject.{field}={rec_subject.get(field)!r}"
            )

    rec_action = recommendation.get("action", {})
    dec_action = decision.get("proposed_action", {})
    for field in ("type", "intent"):
        if dec_action.get(field) is not None and dec_action.get(field) != rec_action.get(field):
            raise ValidationError(
                f"decision {decision.get('decision_id')} proposed_action.{field}={dec_action.get(field)!r} does not match recommendation {rec_id} action.{field}={rec_action.get(field)!r}"
            )

    outcome = decision.get("decision", {}).get("outcome", "unknown")
    if outcome in BLOCKING_OUTCOMES:
        return False, outcome
    if outcome != ALLOWED_EXECUTION_OUTCOME:
        raise ValidationError(f"decision {decision.get('decision_id')} has unsupported outcome={outcome!r}")
    return True, outcome


def validate_bundle(bundle: Dict[str, Any], decisions: Iterable[Dict[str, Any]], *, require_executable: bool) -> Dict[str, Any]:
    if bundle.get("kind") != EXPECTED_BUNDLE_KIND:
        raise ValidationError(f"bundle has invalid kind: {bundle.get('kind')}")

    schema = load_policy_fabric_schema()
    decisions_by_rec = decision_index(decisions, schema)
    checks: List[Dict[str, Any]] = []
    executable_recommendations: List[str] = []
    blocked_recommendations: List[Dict[str, str]] = []

    for recommendation in bundle.get("recommendations", []):
        rec_id = recommendation.get("recommendation_id")
        gate = recommendation.get("policy_gate", {})
        if gate.get("required") is not True:
            checks.append({"recommendation_id": rec_id, "status": "pass", "reason": "policy gate not required"})
            continue

        decision = decisions_by_rec.get(rec_id)
        if not decision:
            if require_executable:
                raise ValidationError(f"recommendation {rec_id} requires policy decision but no matching decision artifact was supplied")
            checks.append({"recommendation_id": rec_id, "status": "blocked", "reason": "missing_decision"})
            blocked_recommendations.append({"recommendation_id": rec_id, "outcome": "missing_decision"})
            continue

        executable, outcome = validate_decision_link(recommendation, decision)
        if executable:
            executable_recommendations.append(rec_id)
            checks.append({"recommendation_id": rec_id, "status": "pass", "reason": "decision_allows_execution"})
        else:
            if require_executable:
                raise ValidationError(f"recommendation {rec_id} is not executable: decision outcome={outcome}")
            blocked_recommendations.append({"recommendation_id": rec_id, "outcome": outcome})
            checks.append({"recommendation_id": rec_id, "status": "blocked", "reason": f"decision_outcome_{outcome}"})

    return {
        "kind": "ProphetOperationsPolicyDecisionValidationReport",
        "schema_version": "v0.1",
        "bundle_id": bundle.get("bundle_id"),
        "summary": {
            "recommendation_count": len(bundle.get("recommendations", [])),
            "decision_count": len(decisions_by_rec),
            "executable_count": len(executable_recommendations),
            "blocked_count": len(blocked_recommendations),
            "require_executable": require_executable,
        },
        "checks": checks,
        "executable_recommendations": executable_recommendations,
        "blocked_recommendations": blocked_recommendations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="ProphetOperationsEvidenceBundle JSON")
    parser.add_argument("--decision", type=Path, action="append", default=[], help="Policy Fabric ProphetOperationsActionDecision JSON. May be supplied more than once.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output validation report JSON")
    parser.add_argument("--require-executable", action="store_true", help="Fail unless every policy-gated recommendation has an allow decision")
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    decisions = [load_json(path) for path in args.decision]
    report = validate_bundle(bundle, decisions, require_executable=args.require_executable)

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
