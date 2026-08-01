#!/usr/bin/env python3
"""Validate the Workspace Control Plane Phase-1 frozen schemas.

For every schema under contracts/workspace-control-plane/schemas:
  * the schema is a valid JSON Schema (Draft 2020-12); and
  * the committed example validates against it.

This is the Phase-1 gate: the object model + manifest schemas are frozen before
runtime code exists, so drift cannot creep in (spec section 8).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "contracts" / "workspace-control-plane"
SCHEMAS = LANE / "schemas"
EXAMPLES = LANE / "examples"

# The eight named frozen objects (spec section 7) plus the canonical event envelope.
REQUIRED = {
    "event.v0",
    "asset.v0",
    "claim.v0",
    "attention-mark.v0",
    "workflow-run.v0",
    "capability-manifest.v0",
    "topic-manifest.v0",
    "catalog-entry.v0",
    "discovery-policy.v0",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    found: set[str] = set()

    for schema_path in sorted(SCHEMAS.glob("*.schema.json")):
        name = schema_path.name.removesuffix(".schema.json")
        found.add(name)
        schema = _load(schema_path)
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001 - report any invalid schema
            errors.append(f"{schema_path.name}: invalid schema: {exc}")
            continue
        example = EXAMPLES / f"{name}.json"
        if not example.exists():
            errors.append(f"{schema_path.name}: missing example {name}.json")
            continue
        for e in sorted(Draft202012Validator(schema).iter_errors(_load(example)), key=lambda e: list(e.path)):
            errors.append(f"{name}.json: {list(e.path)}: {e.message}")

    missing = REQUIRED - found
    if missing:
        errors.append(f"missing required frozen schemas: {sorted(missing)}")

    if errors:
        print("Workspace Control Plane contract validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Workspace Control Plane Phase-1 contracts OK: {len(found)} schemas validated against examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
