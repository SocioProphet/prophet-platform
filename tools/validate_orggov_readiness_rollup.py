#!/usr/bin/env python3
"""Validate OrgGov readiness rollup contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/orggov/orggov-readiness-rollup.v0.1.schema.json"
EXAMPLE = ROOT / "contracts/orggov/orggov-readiness-rollup.v0.1.example.json"


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
    slices = record.get("mergedSlices", [])
    repos = {item["repo"] for item in record["upstreamSnapshot"]["repos"]}
    if record["firstPassStatus"] != "complete":
        fail("firstPassStatus must be complete for the v0 rollup")
    required_count = record["validation"]["requiredSliceCount"]
    observed_count = record["validation"]["observedSliceCount"]
    if observed_count != len(slices):
        fail("validation.observedSliceCount must equal mergedSlices length")
    if required_count != 11 or observed_count != 11:
        fail("OrgGov v0 first pass requires exactly 11 observed slices")
    if len({item["index"] for item in slices}) != len(slices):
        fail("mergedSlices contains duplicate index values")
    if any(item["status"] != "merged" for item in slices):
        fail("all mergedSlices must have status=merged")
    for item in slices:
        if item["repo"] not in repos:
            fail(f"slice repo missing from upstream snapshot: {item['repo']}")
        if not item["artifactRefs"]:
            fail(f"slice {item['index']} has no artifactRefs")
    criteria = record.get("v02RuntimeCriteria", [])
    if len(criteria) < 6:
        fail("expected at least six v0.2 runtime criteria")
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
    print("ok: contracts/orggov/orggov-readiness-rollup.v0.1.example.json validates")
    print("OK: OrgGov readiness rollup validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
