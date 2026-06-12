#!/usr/bin/env python3
"""
Validates repo-governance observation, rule finding, and ledger record fixtures
against their JSON Schema contracts.

Policy gates enforced:
  - Observation: non_claims must not be empty; confidence in [0,1]
  - Rule finding: policy_decision_required=True → action_candidate_ref must not be present
    unless policy_decision_request_ref is also present
  - Ledger record: event_type=action_executed → action_candidate_ref + policy_decision_ref +
    action_scope required
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:
    raise SystemExit("jsonschema is required: python3 -m pip install jsonschema") from exc

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "repo-governance"
SCHEMA_OBS = CONTRACT_DIR / "schemas" / "repo-governance-observation.v0.1.json"
SCHEMA_FINDING = CONTRACT_DIR / "schemas" / "repo-governance-rule-finding.v0.1.json"
SCHEMA_LEDGER = CONTRACT_DIR / "schemas" / "repo-governance-ledger-record.v0.1.json"
FIXTURES = CONTRACT_DIR / "fixtures"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root must be object")
    return data


def schema_for(data: dict[str, Any], schemas: dict[str, Any]) -> dict[str, Any]:
    kind = data.get("kind", "")
    if kind == "RepoGovernanceObservation":
        return schemas["observation"]
    if kind == "RepoGovernanceRuleFinding":
        return schemas["finding"]
    if kind == "RepoGovernanceLedgerRecord":
        return schemas["ledger"]
    raise ValueError(f"unknown kind: {kind!r}")


def check_policy_gates(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    kind = data.get("kind")

    if kind == "RepoGovernanceObservation":
        if not data.get("non_claims"):
            problems.append("non_claims must not be empty")
        conf = data.get("confidence")
        if conf is not None and not (0.0 <= conf <= 1.0):
            problems.append(f"confidence {conf} is outside [0, 1]")

    if kind == "RepoGovernanceRuleFinding":
        if data.get("policy_decision_required") is True:
            if "action_candidate_ref" in data and "policy_decision_request_ref" not in data:
                problems.append(
                    "policy_decision_required=true: action_candidate_ref must not be present "
                    "without policy_decision_request_ref (policy gate violation)"
                )
        if not data.get("non_claims"):
            problems.append("non_claims must not be empty")

    if kind == "RepoGovernanceLedgerRecord":
        if data.get("event_type") == "action_executed":
            if not data.get("action_candidate_ref"):
                problems.append("event_type=action_executed requires action_candidate_ref")
            if not data.get("policy_decision_ref"):
                problems.append("event_type=action_executed requires policy_decision_ref")
            if not data.get("action_scope"):
                problems.append("event_type=action_executed requires action_scope")
        if not data.get("non_claims"):
            problems.append("non_claims must not be empty")

    return problems


def validate_file(path: Path, schemas: dict[str, Any]) -> list[str]:
    try:
        data = load_json(path)
    except Exception as exc:
        return [f"parse error: {exc}"]
    try:
        schema = schema_for(data, schemas)
        jsonschema.validate(data, schema)
    except (jsonschema.ValidationError, ValueError) as exc:
        return [f"schema: {getattr(exc, 'message', str(exc))}"]
    return check_policy_gates(data)


def main() -> int:
    schemas = {
        "observation": load_json(SCHEMA_OBS),
        "finding": load_json(SCHEMA_FINDING),
        "ledger": load_json(SCHEMA_LEDGER),
    }
    failed = False

    valids = sorted(FIXTURES.glob("valid.*.json"))
    if not valids:
        raise SystemExit("missing valid repo-governance fixtures")

    for path in valids:
        problems = validate_file(path, schemas)
        if problems:
            print(f"FAIL (valid): {path.name}")
            for p in problems:
                print(f"  - {p}")
            failed = True
        else:
            print(f"ok: {path.name}")

    rejects = sorted(FIXTURES.glob("reject.*.json"))
    if not rejects:
        raise SystemExit("missing reject repo-governance fixtures")

    for path in rejects:
        problems = validate_file(path, schemas)
        if not problems:
            print(f"FAIL (reject should have failed): {path.name}")
            failed = True
        else:
            print(f"ok (rejected as expected): {path.name}")

    print(
        ("PASS" if not failed else "FAIL")
        + f": repo governance contracts — {len(valids)} valid, {len(rejects)} reject"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
