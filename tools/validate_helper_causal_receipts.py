#!/usr/bin/env python3
"""Validate helper causal receipt evidence envelope JSONL fixtures.

Checks:
  1. JSON parse — each line in each .jsonl file is valid JSON
  2. Schema — each record validates against helper-causal-receipt.schema.v0.1.json
  3. DAG integrity — dag_children refs resolve within the same intent DAG
  4. Policy regression flagging — local_only preview helpers with network, DNS,
     or credential access must have decision=policy_regression (CI gate)
  5. reject_* fixtures — expected-invalid; inverts pass/fail

Validates all *.jsonl files in fixtures/helper-causal-receipts/.
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
SCHEMA = json.loads(
    (ROOT / "schemas" / "helper-causal-receipt.schema.v0.1.json").read_text()
)
FIXTURES = ROOT / "fixtures" / "helper-causal-receipts"

# Capabilities that must trigger policy_regression for local_only preview helpers
POLICY_GATED_CAPS = {"network_send", "dns_resolve", "credential_read"}
POLICY_GATED_CLASSIFICATIONS = {"network_preview", "dns_access", "credential_access"}

schema_validator = jsonschema.Draft202012Validator(SCHEMA)
errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


def validate_dag(records: list[dict], file_label: str) -> None:
    """Check all dag_children IDs resolve within the same file."""
    id_set = {r["event_id"] for r in records}
    for rec in records:
        for child_id in rec.get("dag_children", []):
            if child_id not in id_set:
                fail(f"dag-integrity {file_label}", f"dag_children ref '{child_id}' not found in file")
                return
    ok(f"dag-integrity {file_label}")


def check_policy_regression(records: list[dict], file_label: str) -> None:
    """Local-only preview helpers that emit network/dns/credential must be flagged."""
    for rec in records:
        classification = rec.get("classification", "")
        decision = rec.get("decision", "")
        policy_profile = rec.get("policy_profile", "")
        cap = rec.get("capability", "")
        if (
            "local_only" in policy_profile or "preview" in policy_profile
        ) and (
            classification in POLICY_GATED_CLASSIFICATIONS
            or cap in POLICY_GATED_CAPS
        ) and decision not in ("denied", "policy_regression"):
            fail(
                f"policy-regression-gate {file_label}/{rec['event_id']}",
                f"local/preview helper with {classification}/{cap} must have decision=denied|policy_regression, got '{decision}'"
            )
            return
    ok(f"policy-regression-gate {file_label}")


for path in sorted(FIXTURES.glob("*.jsonl")):
    label = path.name
    is_reject = path.name.startswith("reject_")

    records: list[dict] = []
    parse_ok = True
    for i, line in enumerate(path.read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            fail(f"json-parse {label}:{i+1}", str(e))
            parse_ok = False

    if not parse_ok:
        continue

    ok(f"json-parse {label}")

    # Schema validate each record
    file_schema_errors = []
    for rec in records:
        errs = list(schema_validator.iter_errors(rec))
        for e in errs:
            file_schema_errors.append(f"{rec.get('event_id', '?')}: {e.message}")

    if is_reject:
        # Reject fixtures are expected to trigger policy regression gate
        # Simulate the policy gate check
        regression_events = [r for r in records if r.get("decision") == "policy_regression"]
        if regression_events:
            ok(f"reject-expected policy-regression {label}")
        elif file_schema_errors:
            ok(f"reject-expected schema-error {label}")
        else:
            fail(f"reject-fixture {label}", "expected validation failure but fixture appears valid")
    else:
        if file_schema_errors:
            for e in file_schema_errors:
                fail(f"schema {label}", e)
        else:
            ok(f"schema {label}")
            validate_dag(records, label)
            check_policy_regression(records, label)

# ── Result ────────────────────────────────────────────────────────────────────
passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} helper-causal-receipts checks passed")
