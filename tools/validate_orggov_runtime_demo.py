#!/usr/bin/env python3
"""Validate OrgGov v0.2 runtime-demo contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/orggov/orggov-runtime-demo.v0.2.schema.json"
EXAMPLE = ROOT / "contracts/orggov/orggov-runtime-demo.v0.2.example.json"


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value: Any, expected: str) -> bool:
    actual = json_type_name(value)
    if expected == "number":
        return actual in {"integer", "number"}
    return actual == expected


def validate_schema(schema: dict[str, Any], value: Any, path: str = "$") -> None:
    if "const" in schema and value != schema["const"]:
        fail(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        fail(f"{path}: {value!r} not in enum {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, item) for item in expected_types):
            fail(f"{path}: expected type {expected_types!r}, got {json_type_name(value)!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                fail(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                fail(f"{path}: unexpected properties {extra!r}")
        additional = schema.get("additionalProperties")
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                validate_schema(child_schema, item, f"{path}.{key}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                validate_schema(item_schema, item, f"{path}[{index}]")


def validate_invariants(record: dict[str, Any]) -> None:
    owner_repos = set(record["ownerRepos"])
    if len(owner_repos) != record["validation"]["observedOwnerRepoCount"]:
        fail("validation.observedOwnerRepoCount must equal unique ownerRepos count")
    if record["validation"]["requiredOwnerRepoCount"] != 11 or len(owner_repos) != 11:
        fail("OrgGov v0.2 requires all 11 owner repos")

    required_states = set(record["validation"]["requiredPolicyStates"])
    observed_states = {item["state"] for item in record["policyStateCoverage"]}
    if required_states != {"allow", "allow_with_constraints", "deny", "escalate", "blocked_expected", "revoke"}:
        fail("requiredPolicyStates must be the six canonical OrgGov decision states")
    if required_states - observed_states:
        fail("policyStateCoverage missing states: " + ", ".join(sorted(required_states - observed_states)))
    if not all(item["covered"] is True for item in record["policyStateCoverage"]):
        fail("all policyStateCoverage entries must be covered in the v0.2 spine")

    stage_ids = {stage["stageId"] for stage in record["demoStages"]}
    required_stages = {
        "stage:work-order",
        "stage:control-room",
        "stage:authority",
        "stage:policy",
        "stage:execution",
        "stage:model-tool-receipt",
        "stage:state-integrity",
        "stage:search-trace",
        "stage:scorecard",
        "stage:topology",
    }
    if required_stages - stage_ids:
        fail("demoStages missing required stages: " + ", ".join(sorted(required_stages - stage_ids)))
    for stage in record["demoStages"]:
        if stage["ownerRepo"] not in owner_repos:
            fail(f"stage {stage['stageId']} owner repo is not declared: {stage['ownerRepo']}")
        if not stage["inputRefs"] or not stage["outputRefs"]:
            fail(f"stage {stage['stageId']} must have inputRefs and outputRefs")

    boundary = record["evidenceBoundary"]
    if not boundary["fixtureEvidenceRefs"]:
        fail("fixtureEvidenceRefs must be non-empty")
    if record["demoStatus"] == "fixture_backed" and boundary["runtimeEvidenceRefs"]:
        fail("fixture_backed demos must not claim runtimeEvidenceRefs")
    forbidden = {item.lower() for item in boundary["forbiddenEvidence"]}
    for required in ("secrets", "credentials", "raw private prompts", "private local state"):
        if required not in forbidden:
            fail(f"forbiddenEvidence must include {required!r}")

    if not record["proofObligations"]:
        fail("proofObligations must be non-empty")
    if not all(item["status"] in {"open", "in_progress", "satisfied", "blocked"} for item in record["proofObligations"]):
        fail("proofObligations contain invalid status")
    if not record["runtimePromotionCriteria"]:
        fail("runtimePromotionCriteria must be non-empty")
    if record["provenance"].get("nonSecret") is not True:
        fail("provenance.nonSecret must be true")


def main() -> int:
    try:
        schema = load_json(SCHEMA)
        example = load_json(EXAMPLE)
        validate_schema(schema, example)
        validate_invariants(example)
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("ok: contracts/orggov/orggov-runtime-demo.v0.2.example.json validates")
    print("OK: OrgGov v0.2 runtime demo validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
