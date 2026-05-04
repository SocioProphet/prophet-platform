#!/usr/bin/env python3
"""Validate SourceOS office runtime contract examples."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PAIRS = [
    (
        ROOT / "schemas" / "office" / "office_version_record.schema.json",
        ROOT / "schemas" / "office" / "examples" / "office_version_record.example.json",
    ),
    (
        ROOT / "schemas" / "office" / "office_writeback_record.schema.json",
        ROOT / "schemas" / "office" / "examples" / "office_writeback_record.example.json",
    ),
    (
        ROOT / "schemas" / "office" / "office_policy_decision_record.schema.json",
        ROOT / "schemas" / "office" / "examples" / "office_policy_decision_record.example.json",
    ),
    (
        ROOT / "schemas" / "office" / "office_adapter_profile.schema.json",
        ROOT / "schemas" / "office" / "examples" / "office_adapter_profile.example.json",
    ),
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_pair(schema_path: Path, example_path: Path) -> list[str]:
    schema = load_json(schema_path)
    example = load_json(example_path)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(example), key=lambda error: list(error.path))

    rendered: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.path) or "<root>"
        rendered.append(f"{example_path.relative_to(ROOT)} {location}: {error.message}")
    return rendered


def main() -> int:
    missing = [
        str(path.relative_to(ROOT))
        for pair in CONTRACT_PAIRS
        for path in pair
        if not path.exists()
    ]
    if missing:
        print("Missing office runtime contract validation inputs:")
        for item in missing:
            print(f" - {item}")
        return 1

    failures: list[str] = []
    for schema_path, example_path in CONTRACT_PAIRS:
        failures.extend(validate_pair(schema_path, example_path))

    if failures:
        print("Office runtime contract examples failed validation:")
        for item in failures:
            print(f" - {item}")
        return 1

    print("Office runtime contract examples validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
