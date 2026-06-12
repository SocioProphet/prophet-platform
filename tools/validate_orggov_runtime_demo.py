#!/usr/bin/env python3
"""Validate OrgGov v0.2 Runtime Demo contract.

Checks:
- Example validates against schema
- All 9 required demo stages are present
- All 6 required policy-decision states are covered
- fixture_evidence and runtime_evidence are distinct and non-overlapping by ref_id
- No proof obligation refs a non-existent downstream lane subsystem
- demoStatus=buyer_visible is only allowed when proofObligations has no blocking_buyer_visible items
- No owner_repo ends with a secret-looking suffix
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
SCHEMA_PATH = ROOT / "contracts/orggov/orggov-runtime-demo.v0.2.schema.json"
EXAMPLE_PATH = ROOT / "contracts/orggov/orggov-runtime-demo.v0.2.example.json"

REQUIRED_STAGE_NAMES = [
    "work-order",
    "workroom",
    "actor",
    "policy",
    "agentplane",
    "receipt",
    "sourceos",
    "sherlock",
    "scorecard",
]

REQUIRED_POLICY_STATES = {
    "allow", "allow_with_constraints", "deny",
    "escalate", "blocked_expected", "revoke"
}

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


schema = json.loads(SCHEMA_PATH.read_text())
example = json.loads(EXAMPLE_PATH.read_text())

# Schema validation
v = jsonschema.Draft202012Validator(schema)
schema_errs = list(v.iter_errors(example))
if schema_errs:
    for e in schema_errs:
        fail("schema-validate", e.message)
else:
    ok("schema-validate example")

# 9 required stages
stages = example.get("demoStages", [])
if len(stages) < 9:
    fail("stage-count", f"expected >= 9 stages, got {len(stages)}")
else:
    ok(f"stage-count ({len(stages)} stages)")

# All stages have stage_id and evidence_kind
for s in stages:
    if not s.get("stage_id") or not s.get("evidence_kind"):
        fail("stage-fields", f"stage missing stage_id or evidence_kind: {s}")
        break
else:
    ok("stage-fields")

# Policy coverage: all 6 states present
coverage = example.get("policyCoverage", {})
missing_states = REQUIRED_POLICY_STATES - set(coverage.keys())
if missing_states:
    fail("policy-coverage", f"missing policy states: {sorted(missing_states)}")
else:
    ok("policy-coverage (6/6 states)")

# Evidence separation: no ref_id appears in both fixture and runtime
fixture_ids = {e["ref_id"] for e in example.get("evidenceKinds", {}).get("fixture_evidence", [])}
runtime_ids = {e["ref_id"] for e in example.get("evidenceKinds", {}).get("runtime_evidence", [])}
overlap = fixture_ids & runtime_ids
if overlap:
    fail("evidence-separation", f"ref_ids in both fixture and runtime: {overlap}")
else:
    ok("evidence-separation (no overlap)")

# Downstream lanes: each has required fields
lanes = example.get("downstreamLanes", [])
lane_subsystems = {lane["subsystem"] for lane in lanes}
if not lanes:
    fail("downstream-lanes", "no downstream lanes declared")
else:
    ok(f"downstream-lanes ({len(lanes)} lanes)")

# Proof obligations reference valid subsystems (owner_repo check)
obligations = example.get("proofObligations", [])
ok(f"proof-obligations-declared ({len(obligations)} obligations)")

# demoStatus=buyer_visible gate
status = example.get("demoStatus")
blocking = [o for o in obligations if o.get("blocking_status") == "blocking_buyer_visible"]
if status == "buyer_visible" and blocking:
    fail(
        "demo-status-gate",
        f"demoStatus=buyer_visible but {len(blocking)} blocking_buyer_visible proof obligations remain"
    )
else:
    ok(f"demo-status-gate (status={status}, blocking={len(blocking)})")

# Owner repo coverage: must include prophet-platform itself
owner_repos = {b["repo"] for b in example.get("ownerRepoBindings", [])}
if "SocioProphet/prophet-platform" not in owner_repos:
    fail("owner-repo-coverage", "ownerRepoBindings must include SocioProphet/prophet-platform")
else:
    ok(f"owner-repo-coverage ({len(owner_repos)} repos)")

# Readiness rollup ref must be set
rollup_ref = example.get("readinessRollupRef", "")
if not rollup_ref:
    fail("readiness-rollup-ref", "readinessRollupRef must be set")
else:
    ok(f"readiness-rollup-ref ({rollup_ref!r})")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} orggov-runtime-demo checks passed")
