#!/usr/bin/env python3
"""Validate ADR-035 contract examples and the existing synthetic fixture.

Validates:
  - tests/fixtures/fault-envelope-script-editor-synthetic.json vs FaultEnvelope.v0.1.json
  - contracts/examples/adr-035-*.json vs their respective contract schemas
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"

SCHEMA_CACHE: dict[str, dict] = {}


def load_schema(name: str) -> dict:
    if name not in SCHEMA_CACHE:
        SCHEMA_CACHE[name] = json.loads((CONTRACTS / name).read_text())
    return SCHEMA_CACHE[name]


KIND_TO_SCHEMA = {
    "FaultEnvelope": "FaultEnvelope.v0.1.json",
    "EngineManifest": "EngineManifest.v0.1.json",
    "BoundaryTransition": "BoundaryTransition.v0.1.json",
    "RolloutReceipt": "RolloutReceipt.v0.1.json",
    "DiagnosticRedactionPolicy": "DiagnosticRedactionPolicy.v0.1.json",
}

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


def validate_file(path: Path) -> None:
    label = path.name
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(label, f"JSON parse error: {e}")
        return

    kind = data.get("kind")
    schema_name = KIND_TO_SCHEMA.get(kind)
    if not schema_name:
        fail(label, f"unknown kind '{kind}' — no schema mapping")
        return

    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    errs = list(validator.iter_errors(data))
    if errs:
        for e in errs:
            fail(label, e.message)
    else:
        ok(label)


# ── Existing synthetic fixture ────────────────────────────────────────────────
validate_file(ROOT / "tests" / "fixtures" / "fault-envelope-script-editor-synthetic.json")

# ── ADR-035 worked example fixtures ──────────────────────────────────────────
for path in sorted((CONTRACTS / "examples").glob("adr-035-*.json")):
    validate_file(path)

# ── Result ────────────────────────────────────────────────────────────────────
passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} ADR-035 contract checks passed")
