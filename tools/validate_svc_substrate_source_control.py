#!/usr/bin/env python3
"""Validate svc.substrate.source-control platform service manifest.

Checks:
  1. JSON parses cleanly.
  2. Required top-level fields present.
  3. scaffold_baseline references the canonical commit.
  4. pr_a_status.deployment_ready is false (PR-A does not imply readiness).
  5. All five runtime_prerequisites are present by id.
  6. authority_boundary.owner is prophet-platform.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "PlatformServiceManifest.svc.substrate.source-control.v0.1.json"

CANONICAL_COMMIT = "5d85ab6a24502f60f15ef829235b6288a289d47e"
REQUIRED_PREREQ_IDS = {
    "prereq_gateway",
    "prereq_direct_bypass_controls",
    "prereq_key_rotation",
    "prereq_audit_verification",
    "prereq_receipt_export",
}
REQUIRED_FIELDS = [
    "schema_version", "kind", "service_id", "runtime_posture",
    "scaffold_baseline", "deployment_topology", "policy_dependencies",
    "grant_dependencies", "ledger_dependencies", "evidence_receipts",
    "pr_a_status", "runtime_prerequisites", "authority_boundary",
]

errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


try:
    manifest = json.loads(CONTRACT.read_text())
except json.JSONDecodeError as e:
    fail("json-parse", str(e))
    sys.exit(1)

ok("json-parse")

missing = [f for f in REQUIRED_FIELDS if f not in manifest]
if missing:
    fail("required-fields", f"missing: {missing}")
else:
    ok("required-fields")

if manifest.get("service_id") == "svc.substrate.source-control":
    ok("service-id")
else:
    fail("service-id", f"expected 'svc.substrate.source-control', got '{manifest.get('service_id')}'")

scaffold = manifest.get("scaffold_baseline", {})
if scaffold.get("commit") == CANONICAL_COMMIT:
    ok("scaffold-commit")
else:
    fail("scaffold-commit", f"expected {CANONICAL_COMMIT}, got '{scaffold.get('commit')}'")

pr_a = manifest.get("pr_a_status", {})
if pr_a.get("is_pr_a") is True and pr_a.get("deployment_ready") is False:
    ok("pr-a-not-deployment-ready")
else:
    fail("pr-a-not-deployment-ready", "pr_a_status must have is_pr_a=true and deployment_ready=false")

prereqs = {p["id"] for p in manifest.get("runtime_prerequisites", [])}
missing_prereqs = REQUIRED_PREREQ_IDS - prereqs
if missing_prereqs:
    fail("runtime-prerequisites", f"missing prereqs: {missing_prereqs}")
else:
    ok("runtime-prerequisites")

authority = manifest.get("authority_boundary", {})
if authority.get("owner") == "prophet-platform":
    ok("authority-boundary-owner")
else:
    fail("authority-boundary-owner", f"expected 'prophet-platform', got '{authority.get('owner')}'")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} svc.substrate.source-control checks passed")
