#!/usr/bin/env python3
"""Validate mutation and evidence accountability fixtures.

Validates MutationReceipt and EvidencePipelineReceipt fixtures against schemas.
Enforces policy gate: a service claiming compromise_clearance=cleared with
degraded_sensor or insufficient_for_clearance evidence_quality must be rejected.
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
SCHEMA_DIR = ROOT / "schemas" / "mutation-evidence"
FIXTURES = ROOT / "fixtures" / "mutation-evidence"

MUTATION_SCHEMA = json.loads((SCHEMA_DIR / "MutationReceipt.schema.v0.1.json").read_text())
PIPELINE_SCHEMA = json.loads((SCHEMA_DIR / "EvidencePipelineReceipt.schema.v0.1.json").read_text())

BLIND_QUALITIES = {"degraded_sensor", "insufficient_for_clearance"}

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


def detect_schema(data: dict) -> tuple[str, dict] | None:
    if "mutation_id" in data:
        return "MutationReceipt", MUTATION_SCHEMA
    if "pipeline_receipt_id" in data:
        return "EvidencePipelineReceipt", PIPELINE_SCHEMA
    return None


for path in sorted(FIXTURES.glob("*.json")):
    is_reject = path.name.startswith("reject_")
    label = path.name

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"json-parse {label}", str(e))
        continue

    ok(f"json-parse {label}")

    detected = detect_schema(data)
    if detected is None:
        ok(f"skip {label} (unknown schema)")
        continue

    kind, schema = detected
    v = jsonschema.Draft202012Validator(schema)
    schema_errs = list(v.iter_errors(data))

    # Extra policy gate check
    policy_gate_err = None
    if kind == "MutationReceipt":
        clearance = data.get("compromise_clearance")
        quality = data.get("evidence_quality", "")
        if clearance == "cleared" and quality in BLIND_QUALITIES:
            policy_gate_err = f"clearance=cleared with evidence_quality={quality} violates policy gate"

    has_errors = bool(schema_errs) or bool(policy_gate_err)

    if is_reject:
        if has_errors:
            ok(f"reject-expected {label} ({kind})")
        else:
            fail(f"reject-fixture {label}", "expected failure but fixture appears valid")
    else:
        if schema_errs:
            for e in schema_errs:
                fail(f"schema {label}", e.message)
        elif policy_gate_err:
            fail(f"policy-gate {label}", policy_gate_err)
        else:
            ok(f"schema {label} ({kind})")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} mutation-evidence checks passed")
