#!/usr/bin/env python3
"""Validate Workroom v0.1 object-model fixtures against schemas.

Validates:
  - fixtures/workroom/*.json — each JSON object or embedded sub-object is matched
    to its schema by the schema_version + implied kind from schema title
  - Causal claim constraint: is_causal=true requires evidence_refs (minItems 1) or
    non_evidential_reason
  - High-risk action constraint: RemediationPlan steps with risk_level high/critical
    must have action_grant_ref
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
SCHEMA_DIR = ROOT / "schemas" / "workroom"
FIXTURES = ROOT / "fixtures" / "workroom"

SCHEMA_MAP = {
    "BehavioralDivergenceEvent": json.loads((SCHEMA_DIR / "BehavioralDivergenceEvent.schema.v0.1.json").read_text()),
    "EvidencePacket": json.loads((SCHEMA_DIR / "EvidencePacket.schema.v0.1.json").read_text()),
    "RCAClaim": json.loads((SCHEMA_DIR / "RCAClaim.schema.v0.1.json").read_text()),
    "InvestigationRunReceipt": json.loads((SCHEMA_DIR / "InvestigationRunReceipt.schema.v0.1.json").read_text()),
    "RemediationPlan": json.loads((SCHEMA_DIR / "RemediationPlan.schema.v0.1.json").read_text()),
    "ActionGrant": json.loads((SCHEMA_DIR / "ActionGrant.schema.v0.1.json").read_text()),
    "RegressionFixture": json.loads((SCHEMA_DIR / "RegressionFixture.schema.v0.1.json").read_text()),
}

KEY_TO_KIND = {
    "divergence_event": "BehavioralDivergenceEvent",
    "evidence_packet": "EvidencePacket",
    "rca_claim": "RCAClaim",
    "investigation_run_receipt": "InvestigationRunReceipt",
    "remediation_plan": "RemediationPlan",
    "action_grant": "ActionGrant",
    "regression_fixture": "RegressionFixture",
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

    for key, kind in KEY_TO_KIND.items():
        if key not in data:
            continue
        rec = data[key]
        label = f"{path.name}/{key}"
        schema = SCHEMA_MAP[kind]
        validator = jsonschema.Draft202012Validator(schema)
        errs = list(validator.iter_errors(rec))
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

print(f"\n{passed} workroom schema checks passed")
