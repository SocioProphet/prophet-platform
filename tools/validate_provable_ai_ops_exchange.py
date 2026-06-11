#!/usr/bin/env python3
"""Validate provable AI operations exchange fixture bundle.

Checks:
  1. JSON syntax — all fixture files parse without error
  2. Required fields — each record type has its mandatory fields
  3. Referential integrity — all *_ref / *_refs values resolve within the bundle
  4. Custody gate — IntelligenceBrief with certification_level > 1 must have
     at least one custody_event_ref (blocks Level 2+ certification without chain)
  5. Reject fixtures — files prefixed reject_ must trigger a validation failure;
     the validator treats them as expected-invalid and inverts the pass/fail
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "provable-ai-ops-exchange"

REQUIRED_FIELDS: dict[str, list[str]] = {
    "IntelligenceBrief": [
        "record_type", "record_id", "title", "summary", "authored_by",
        "authored_at", "classification", "certification_level",
        "claim_refs", "evidence_refs", "artifact_refs", "custody_event_refs",
    ],
    "Claim": [
        "record_type", "record_id", "claim_text", "claim_type",
        "asserted_by", "asserted_at", "status",
    ],
    "Evidence": [
        "record_type", "record_id", "evidence_kind", "description",
        "produced_by", "produced_at",
    ],
    "Artifact": [
        "record_type", "record_id", "artifact_kind", "name",
        "created_by", "created_at", "integrity_hash",
    ],
    "PolicyDecision": [
        "record_type", "record_id", "policy_id", "decision",
        "decided_by", "decided_at", "applicable_to",
    ],
    "AgentAction": [
        "record_type", "record_id", "action_type", "actor_id",
        "performed_at", "action_outcome",
    ],
    "SpecialistCredential": [
        "record_type", "record_id", "holder_id", "credential_type",
        "granted_by", "granted_at",
    ],
    "ReviewAttestation": [
        "record_type", "record_id", "attested_by", "credential_ref",
        "attested_at", "subject_refs", "attestation_outcome",
    ],
    "CustodyEvent": [
        "record_type", "record_id", "event_kind", "subject_ref",
        "actor_id", "occurred_at", "integrity_hash",
    ],
}

errors: list[str] = []
results: list[bool] = []


def fail(msg: str) -> None:
    errors.append(msg)
    results.append(False)


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def collect_records(data: object) -> list[dict]:
    """Flatten dicts, lists, and nested dicts-of-dicts into a flat record list."""
    if isinstance(data, dict):
        if "record_type" in data:
            return [data]
        records = []
        for v in data.values():
            records.extend(collect_records(v))
        return records
    if isinstance(data, list):
        records = []
        for item in data:
            records.extend(collect_records(item))
        return records
    return []


# ── Load all fixture files ────────────────────────────────────────────────────
all_records: list[dict] = []
reject_records: list[dict] = []

fixture_files = sorted(FIXTURES.glob("*.json"))
if not fixture_files:
    fail("No fixture files found in fixtures/provable-ai-ops-exchange/")

for path in fixture_files:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"JSON parse error in {path.name}: {e}")
        continue

    records = collect_records(data)
    is_reject = path.name.startswith("reject_")
    if is_reject:
        reject_records.extend(records)
    else:
        all_records.extend(records)

    ok(f"json-parse {path.name}")

# ── Build ID index for referential integrity ──────────────────────────────────
id_index: set[str] = set()
for rec in all_records:
    rid = rec.get("record_id") or rec.get("run_id")
    if rid:
        id_index.add(rid)

# ── Required fields check ─────────────────────────────────────────────────────
for rec in all_records:
    rtype = rec.get("record_type", "Unknown")
    rid = rec.get("record_id", "<no id>")
    label = f"{rtype}/{rid}"
    required = REQUIRED_FIELDS.get(rtype, [])
    missing = [f for f in required if f not in rec]
    if missing:
        fail(f"required-fields {label}: missing {missing}")
    else:
        ok(f"required-fields {label}")

# ── Referential integrity ─────────────────────────────────────────────────────
def check_refs(rec: dict, field: str, label: str) -> None:
    refs = rec.get(field)
    if refs is None:
        return
    if isinstance(refs, str):
        refs = [refs]
    for ref in refs:
        if ref not in id_index:
            fail(f"broken-ref {label}.{field}: '{ref}' not found in bundle")

ref_fields = [
    "claim_refs", "evidence_refs", "artifact_refs", "custody_event_refs",
    "policy_decision_ref", "attestation_ref", "specialist_credential_ref",
    "credential_ref", "subject_refs", "benchmark_pack_ref",
    "original_run_ref",
    # authority_dependency_id is a cross-system ref resolved by AgentPlane, not in-bundle
]

for rec in all_records:
    rtype = rec.get("record_type", "Unknown")
    rid = rec.get("record_id", "<no id>")
    label = f"{rtype}/{rid}"
    checked = False
    for field in ref_fields:
        if field in rec:
            check_refs(rec, field, label)
            checked = True
    if checked:
        ok(f"referential-integrity {label}")

# ── Custody gate: Level > 1 requires custody_event_refs ──────────────────────
for rec in all_records:
    if rec.get("record_type") != "IntelligenceBrief":
        continue
    rid = rec.get("record_id", "<no id>")
    level = rec.get("certification_level", 1)
    custody = rec.get("custody_event_refs", [])
    if level > 1 and not custody:
        fail(f"custody-gate IntelligenceBrief/{rid}: certification_level={level} requires at least one custody_event_ref")
    else:
        ok(f"custody-gate IntelligenceBrief/{rid} (level={level})")

# ── Reject fixture inversions ─────────────────────────────────────────────────
for rec in reject_records:
    rtype = rec.get("record_type", "Unknown")
    rid = rec.get("record_id", "<no id>")
    label = f"{rtype}/{rid}"
    level = rec.get("certification_level", 1)
    custody = rec.get("custody_event_refs", [])
    if level > 1 and not custody:
        ok(f"reject-expected custody-gate {label}")
    else:
        fail(f"reject-fixture {label}: expected validation failure but record appears valid")

# ── Final result ──────────────────────────────────────────────────────────────
passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} provable-ai-ops-exchange checks passed")
