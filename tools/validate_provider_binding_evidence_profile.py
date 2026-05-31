#!/usr/bin/env python3
"""Validate ProviderBinding evidence profile examples against schema."""

from __future__ import annotations

from pathlib import Path
import json

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "specs" / "brokerage" / "schemas" / "provider-binding-evidence-profile.schema.json"
EXAMPLE_PATH = ROOT / "specs" / "brokerage" / "events" / "examples" / "provider-binding-evidence-profile.example.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    missing = [str(path) for path in (SCHEMA_PATH, EXAMPLE_PATH) if not path.exists()]
    if missing:
        print("Missing ProviderBinding evidence profile validation inputs:")
        for item in missing:
            print(f" - {item}")
        return 1

    schema = load_json(SCHEMA_PATH)
    example = load_json(EXAMPLE_PATH)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(example), key=lambda error: list(error.path))

    if errors:
        print("ProviderBinding evidence profile example failed schema validation:")
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f" - {location}: {error.message}")
        return 1

    print("ProviderBinding evidence profile example validates against schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
