#!/usr/bin/env python3
"""Validate semantic activation envelopes and semantic diff specs.

Validates SemanticActivationEnvelope and SemanticDiffSpec fixtures against schemas.
Enforces that provenance_hash matches sha256:<64-hex> format for envelopes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas" / "semantic-governance"
FIXTURES = ROOT / "fixtures" / "semantic-governance"

ENVELOPE_SCHEMA = json.loads(
    (SCHEMA_DIR / "SemanticActivationEnvelope.schema.v0.1.json").read_text()
)
DIFF_SCHEMA = json.loads(
    (SCHEMA_DIR / "SemanticDiffSpec.schema.v0.1.json").read_text()
)

HASH_RE = re.compile(r"^sha256:[A-Fa-f0-9]{64}$")

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


def detect_schema(data: dict) -> tuple[str, dict] | None:
    if "envelope_id" in data and "asset_id" in data and "provenance_hash" in data:
        return "SemanticActivationEnvelope", ENVELOPE_SCHEMA
    if "diff_id" in data and "from_envelope_id" in data:
        return "SemanticDiffSpec", DIFF_SCHEMA
    # reject fixtures may be missing required fields — try envelope first
    if "envelope_id" in data:
        return "SemanticActivationEnvelope", ENVELOPE_SCHEMA
    if "diff_id" in data:
        return "SemanticDiffSpec", DIFF_SCHEMA
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

    # Extra hash format gate (belt-and-suspenders — also enforced by schema pattern)
    hash_err = None
    if kind == "SemanticActivationEnvelope":
        ph = data.get("provenance_hash", "")
        if ph and not HASH_RE.match(ph):
            hash_err = f"provenance_hash '{ph}' does not match sha256:<64-hex>"

    has_errors = bool(schema_errs) or bool(hash_err)

    if is_reject:
        if has_errors:
            ok(f"reject-expected {label} ({kind})")
        else:
            fail(f"reject-fixture {label}", "expected failure but fixture appears valid")
    else:
        if schema_errs:
            for e in schema_errs:
                fail(f"schema {label}", e.message)
        elif hash_err:
            fail(f"hash-gate {label}", hash_err)
        else:
            ok(f"schema {label} ({kind})")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} semantic-governance checks passed")
