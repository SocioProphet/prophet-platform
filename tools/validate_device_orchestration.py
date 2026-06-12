#!/usr/bin/env python3
"""Validate sovereign device orchestration contracts and fixtures.

Validates all fixtures/device-orchestration/*.json against their respective
schemas. No live device/cloud credentials required.
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
SCHEMA_DIR = ROOT / "schemas" / "device-orchestration"
FIXTURES = ROOT / "fixtures" / "device-orchestration"

SCHEMA_MAP = {
    "device_node": json.loads((SCHEMA_DIR / "DeviceGraphNode.schema.v0.1.json").read_text()),
    "orchestration_event": json.loads((SCHEMA_DIR / "OrchestrationEvent.schema.v0.1.json").read_text()),
    "routine": json.loads((SCHEMA_DIR / "RoutineObject.schema.v0.1.json").read_text()),
    "evidence_receipt": json.loads((SCHEMA_DIR / "OrchestrationEvidenceReceipt.schema.v0.1.json").read_text()),
    "adapter_health": json.loads((SCHEMA_DIR / "AdapterHealthReceipt.schema.v0.1.json").read_text()),
}

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


for path in sorted(FIXTURES.glob("*.json")):
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"json-parse {path.name}", str(e))
        continue

    ok(f"json-parse {path.name}")

    for key, schema in SCHEMA_MAP.items():
        if key not in data:
            continue
        label = f"{path.name}/{key}"
        validator = jsonschema.Draft202012Validator(schema)
        errs = list(validator.iter_errors(data[key]))
        if errs:
            for e in errs:
                fail(f"schema {label}", e.message)
        else:
            ok(f"schema {label}")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} device-orchestration checks passed")
