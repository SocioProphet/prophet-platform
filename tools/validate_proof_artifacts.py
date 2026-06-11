#!/usr/bin/env python3
"""Validate Trust-First proof artifacts against schema and checker rules.

Checker rules (beyond JSON Schema):
  1. inputs_hash must match sha256:[A-Fa-f0-9]{64} exactly.
  2. PROVED artifacts for kms_key_usage must have at minimum:
     KMS.Decrypt and Identity.Attest in coverage (required families).
  3. reject_* fixtures are expected-invalid — the checker inverts pass/fail.

Validates all *.json files in examples/ that are proof artifacts
(have schema_version + claim + result).
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
SCHEMA = json.loads((ROOT / "schemas" / "proof-artifact.schema.json").read_text())
EXAMPLES = ROOT / "examples"

# Minimum coverage families required before a PROVED result is accepted
PROVED_REQUIRED_COVERAGE: dict[str, list[str]] = {
    "kms_key_usage": ["KMS.Decrypt", "Identity.Attest"],
    "boundary_non_escape": ["Scope.Enter", "Scope.Exit"],
    "ifc_no_flow": ["Data.Read", "Data.Write"],
    "capability_confinement": ["Identity.Attest"],
    "usage_budget": ["Token.Consume"],
}

HASH_RE = re.compile(r"^sha256:[A-Fa-f0-9]{64}$")

validator = jsonschema.Draft202012Validator(SCHEMA)
errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


def check_artifact(artifact: dict, label: str) -> list[str]:
    """Return list of checker-rule violations (empty = clean)."""
    violations: list[str] = []

    # Rule 1: inputs_hash format
    ih = artifact.get("inputs_hash", "")
    if not HASH_RE.match(ih):
        violations.append(f"inputs_hash '{ih}' does not match sha256:<64-hex>")

    # Rule 2: PROVED coverage families
    if artifact.get("result") == "PROVED":
        claim_kind = artifact.get("claim", {}).get("kind", "")
        required = PROVED_REQUIRED_COVERAGE.get(claim_kind, [])
        coverage = set(artifact.get("assumptions", {}).get("coverage", []))
        missing = [f for f in required if f not in coverage]
        if missing:
            violations.append(
                f"PROVED result for {claim_kind} missing required coverage families: {missing}"
            )

    return violations


for path in sorted(EXAMPLES.glob("*.json")):
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(path.name, f"JSON parse error: {e}")
        continue

    # Only validate files that look like proof artifacts
    if not ("schema_version" in data and "claim" in data and "result" in data):
        ok(f"skip {path.name} (not a proof artifact)")
        continue

    is_reject = path.name.startswith("reject_")
    label = path.name

    schema_errors = list(validator.iter_errors(data))
    checker_violations = check_artifact(data, label)

    has_errors = bool(schema_errors or checker_violations)

    if is_reject:
        if has_errors:
            ok(f"reject-expected {label}")
        else:
            fail(f"reject-fixture {label}", "expected validation failure but artifact appears valid")
    else:
        if schema_errors:
            for e in schema_errors:
                fail(label, f"schema: {e.message}")
        elif checker_violations:
            for v in checker_violations:
                fail(label, f"checker: {v}")
        else:
            ok(label)

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} proof-artifact checks passed")
