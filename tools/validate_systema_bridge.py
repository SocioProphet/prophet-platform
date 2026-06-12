#!/usr/bin/env python3
"""Validate Systema evidence refs consumed by the prophet-platform runtime bridge.

Validates required fields on each evidence ref record without replacing upstream
schemas (ProCybernetica, Ontogenesis, Sherlock, GAIA, AgentPlane, SourceOS).

Usage:
  python3 tools/validate_systema_bridge.py [path/to/evidence-refs.json]

Defaults to contracts/systema-evidence-ref.example.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = ROOT / "contracts" / "systema-evidence-ref.example.json"

REQUIRED_FIELDS = ["ref_type", "canonical_source", "ref_id", "observed_at",
                   "conformance_claim", "evidence_quality"]

VALID_REF_TYPES = {
    "procybernetica_profile",
    "procybernetica_conformance",
    "ontogenesis_concept",
    "sherlock_catalog",
    "gaia_scenario",
    "agentplane_artifact",
    "sourceos_event",
    "delivery_excellence_metric",
}

VALID_QUALITIES = {"complete", "partial", "degraded", "insufficient"}

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET

try:
    data = json.loads(target.read_text())
except json.JSONDecodeError as e:
    fail("json-parse", str(e))
    sys.exit(1)

ok("json-parse")

if not isinstance(data, list):
    fail("top-level-type", "expected JSON array of evidence ref records")
    sys.exit(1)

ok("top-level-type")

if not data:
    fail("non-empty", "evidence ref list is empty")
    sys.exit(1)

ok("non-empty")

for i, rec in enumerate(data):
    label = f"ref[{i}]/{rec.get('ref_id', '?')}"

    missing = [f for f in REQUIRED_FIELDS if f not in rec]
    if missing:
        fail(f"required-fields {label}", f"missing: {missing}")
        continue
    ok(f"required-fields {label}")

    if rec["ref_type"] not in VALID_REF_TYPES:
        fail(f"ref-type {label}", f"unknown ref_type '{rec['ref_type']}'")
    else:
        ok(f"ref-type {label}")

    if rec["evidence_quality"] not in VALID_QUALITIES:
        fail(f"evidence-quality {label}", f"unknown quality '{rec['evidence_quality']}'")
    else:
        ok(f"evidence-quality {label}")

    if not rec.get("canonical_source", "").strip():
        fail(f"canonical-source {label}", "canonical_source must be non-empty")
    else:
        ok(f"canonical-source {label}")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} systema-bridge checks passed")
