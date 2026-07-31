#!/usr/bin/env python3
"""Validate the Web Intelligence lane contracts.

For every event schema under contracts/web-intel/events:
  * the schema itself is a valid JSON Schema (Draft 2020-12); and
  * the committed example payload validates against it.

Also validates the shared metric-claim envelope schema. Exits non-zero on any
failure so the lane's CI gate fails closed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "contracts" / "web-intel"
EVENTS = LANE / "events"
EXAMPLES = LANE / "examples"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _example_name(schema_path: Path) -> str:
    # webintel.site_audit.completed.v0.schema.json -> site_audit.completed.json
    stem = schema_path.name
    stem = stem.removeprefix("webintel.").removesuffix(".v0.schema.json")
    return f"{stem}.json"


def main() -> int:
    errors: list[str] = []

    envelope = LANE / "schemas" / "metric-claim-envelope.v0.schema.json"
    if not envelope.exists():
        errors.append("missing metric-claim-envelope.v0.schema.json")
    else:
        Draft202012Validator.check_schema(_load(envelope))

    schema_files = sorted(EVENTS.glob("*.schema.json"))
    if not schema_files:
        errors.append("no event schemas found under contracts/web-intel/events")

    for schema_path in schema_files:
        schema = _load(schema_path)
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001 - report any invalid schema
            errors.append(f"{schema_path.name}: invalid schema: {exc}")
            continue

        example_path = EXAMPLES / _example_name(schema_path)
        if not example_path.exists():
            errors.append(f"{schema_path.name}: missing example {example_path.name}")
            continue

        validator = Draft202012Validator(schema)
        for e in sorted(validator.iter_errors(_load(example_path)), key=lambda e: list(e.path)):
            errors.append(f"{example_path.name}: {list(e.path)}: {e.message}")

    if errors:
        print("Web Intelligence contract validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Web Intelligence contracts OK: {len(schema_files)} event schemas validated against examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
