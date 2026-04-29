#!/usr/bin/env python3
"""Validate Professional Intelligence OS platform contracts and manifest.

This validator is deliberately dependency-light. It validates the JSON fixtures against
the schema subset used by the seed Professional Intelligence contracts and checks that
contract paths referenced by `professional-intelligence.manifest.yaml` exist.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "professional-intelligence.manifest.yaml"
SCHEMA_EXAMPLES = [
    (
        ROOT / "contracts/evidence/adoption-event.schema.json",
        ROOT / "contracts/evidence/adoption-event.v0.1.example.json",
    ),
    (
        ROOT / "contracts/institution/institution-entity.schema.json",
        ROOT / "contracts/institution/institution-entity.v0.1.example.json",
    ),
    (
        ROOT / "contracts/policy/obligation.schema.json",
        ROOT / "contracts/policy/obligation.v0.1.example.json",
    ),
    (
        ROOT / "contracts/risk/conflict-check.schema.json",
        ROOT / "contracts/risk/conflict-check.v0.1.example.json",
    ),
]


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
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
        raise ValidationError(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: {value!r} not in enum {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, item) for item in expected_types):
            raise ValidationError(
                f"{path}: expected type {expected_types!r}, got {json_type_name(value)!r}"
            )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ValidationError(f"{path}: missing required property {key!r}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValidationError(f"{path}: unexpected properties {extra!r}")

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


def validate_manifest_contract_paths() -> None:
    if not MANIFEST.exists():
        raise ValidationError("missing professional-intelligence.manifest.yaml")

    text = MANIFEST.read_text(encoding="utf-8")
    contract_paths = re.findall(r"^\s*-\s+(contracts/[^\s#]+)\s*$", text, flags=re.MULTILINE)
    if not contract_paths:
        raise ValidationError("manifest does not declare any contractPaths entries")

    missing = [path for path in contract_paths if not (ROOT / path).exists()]
    if missing:
        joined = ", ".join(missing)
        raise ValidationError(f"manifest references missing contract paths: {joined}")

    print(f"ok: manifest references {len(contract_paths)} existing contract paths")


def validate_examples() -> None:
    for schema_path, example_path in SCHEMA_EXAMPLES:
        schema = load_json(schema_path)
        example = load_json(example_path)
        validate_schema(schema, example)
        print(
            "ok: "
            f"{example_path.relative_to(ROOT)} validates against {schema_path.relative_to(ROOT)}"
        )


def main() -> int:
    try:
        validate_manifest_contract_paths()
        validate_examples()
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    print("OK: Professional Intelligence validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
