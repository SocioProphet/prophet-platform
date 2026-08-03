#!/usr/bin/env python3
"""Validate Evidence-Cover Graphs against schema + registry checker rules.

Standards-layer artifact (evidence_cover_registry_spec_v0_1) landed as spec-as-code:
evidence sufficiency expressed as *covers* (hyperedges) over content-addressed
evidence items, with *overlap* (gluing) constraints and disclosure *tiers*.

Two verdicts are computed per graph:

  1. ValidateGraph (structural) -- checker rules beyond JSON Schema:
       C1. EvidenceItem ids are unique within the graph.
       C2. Every cover.evidence_item_ids reference resolves to an evidence item.
       C3. Every overlap_requirement.covers reference resolves to a cover.
       C4. Every cover.claim_id equals the graph claim_id (no cross-claim smuggling).
       C5. If tier_policy present, every cover.tier is in tier_policy.tier_order.
     reject_* fixtures are expected-invalid: the checker inverts pass/fail on them.

  2. Gluing gate (CheckOverlapConsistency) -- runs only on structurally-valid graphs:
       for each overlap requirement, evidence items whose <TYPE> matches the path
       prefix, drawn from every listed cover, MUST agree on the trailing field
       (only .digest_sha256 is checkable from the graph today). Disagreement =>
       INCONCLUSIVE with a deterministic, content-addressed RepairRequest.
     glue_inconclusive_* fixtures are structurally valid but MUST glue to INCONCLUSIVE
     with a repair request; every other structurally-valid fixture MUST glue to GLUABLE.

The RepairRequest determinism law (spec s.EmitRepairRequest) is enforced with teeth:
the repair request is emitted twice and its canonical sha256 must be identical.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas" / "evidence-cover-graph.schema.json").read_text())
FIXTURES = ROOT / "contracts" / "evidence" / "cover"

validator = jsonschema.Draft202012Validator(SCHEMA)
errors: list[str] = []
results: list[bool] = []


def ok(label: str) -> None:
    print(f"PASS {label}")
    results.append(True)


def fail(label: str, reason: str) -> None:
    errors.append(f"FAIL {label}: {reason}")
    results.append(False)


def canon(obj: object) -> bytes:
    """Project CanonicalizationProfile: UTF-8 JSON, keys sorted, tight separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def validate_graph(graph: dict) -> list[str]:
    """ValidateGraph structural checker rules (C1..C5). Empty list = clean."""
    v: list[str] = []
    items = graph.get("evidence_items", [])
    item_ids = [it.get("id") for it in items]

    # C1: unique evidence ids
    dupes = sorted({i for i in item_ids if item_ids.count(i) > 1})
    if dupes:
        v.append(f"C1 duplicate evidence_item ids: {dupes}")
    item_id_set = set(item_ids)

    covers = graph.get("covers", [])
    cover_ids = {c.get("cover_id") for c in covers}
    graph_claim = graph.get("claim_id")

    for c in covers:
        cid = c.get("cover_id")
        # C2: cover evidence refs resolve
        missing = [e for e in c.get("evidence_item_ids", []) if e not in item_id_set]
        if missing:
            v.append(f"C2 cover '{cid}' references unknown evidence items: {missing}")
        # C4: cover claim_id matches graph claim_id
        if c.get("claim_id") != graph_claim:
            v.append(
                f"C4 cover '{cid}' claim_id '{c.get('claim_id')}' != graph claim_id '{graph_claim}'"
            )
        # C5: tier in tier_order (only if policy present)
        tp = graph.get("tier_policy")
        if tp and c.get("tier") not in tp.get("tier_order", []):
            v.append(f"C5 cover '{cid}' tier '{c.get('tier')}' not in tier_policy.tier_order")

    # C3: overlap requirement cover refs resolve
    for ov in graph.get("overlap_requirements", []):
        oid = ov.get("overlap_id")
        bad = [c for c in ov.get("covers", []) if c not in cover_ids]
        if bad:
            v.append(f"C3 overlap '{oid}' references unknown covers: {bad}")

    return v


def gluing_verdict(graph: dict) -> tuple[str, dict | None]:
    """CheckOverlapConsistency. Returns (verdict, repair_request_or_None).

    verdict in {"GLUABLE", "INCONCLUSIVE"}. Only .digest_sha256 paths are checkable
    from the graph (evidence content is off-graph; digests stand in for it)."""
    items_by_id = {it["id"]: it for it in graph.get("evidence_items", [])}
    covers_by_id = {c["cover_id"]: c for c in graph.get("covers", [])}

    for ov in graph.get("overlap_requirements", []):
        for path in ov.get("must_agree_on", []):
            ev_type, _, field = path.partition(".")
            if field != "digest_sha256":
                # Not carriable in-graph; spec leaves richer paths to a runtime verifier.
                continue
            observed: set[str] = set()
            for cover_id in ov.get("covers", []):
                cover = covers_by_id.get(cover_id, {})
                for eid in cover.get("evidence_item_ids", []):
                    it = items_by_id.get(eid)
                    if it and it.get("type") == ev_type:
                        observed.add(it["digest_sha256"])
            if len(observed) > 1:
                repair = {
                    "repair_request_version": 1,
                    "claim_id": graph["claim_id"],
                    "reason": "overlap_mismatch",
                    "details": {
                        "overlap_id": ov["overlap_id"],
                        "path": path,
                        "conflicting_values": sorted(observed),
                    },
                    "requested_actions": [
                        {"action": "provide_evidence", "evidence_type": ev_type},
                        {"action": "reconcile_registry", "strategy": "single_authoritative_snapshot"},
                    ],
                }
                return "INCONCLUSIVE", repair
    return "GLUABLE", None


MIN_FIXTURES = 8
fixture_paths = sorted(FIXTURES.glob("*.json"))
if len(fixture_paths) < MIN_FIXTURES:
    print(
        f"ERR: expected at least {MIN_FIXTURES} *.json fixtures under "
        f"{FIXTURES.relative_to(ROOT)}, found {len(fixture_paths)} -- an empty or thinned "
        f"fixture set silently disables this validator",
        file=sys.stderr,
    )
    sys.exit(1)

for path in fixture_paths:
    label = path.name
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(label, f"JSON parse error: {e}")
        continue

    is_reject = label.startswith("reject_")
    is_glue_inconclusive = label.startswith("glue_inconclusive_")

    schema_errors = list(validator.iter_errors(data))
    checker_violations = validate_graph(data) if not schema_errors else []
    structurally_invalid = bool(schema_errors or checker_violations)

    if is_reject:
        if structurally_invalid:
            ok(f"reject-expected {label}")
        else:
            fail(f"reject-fixture {label}", "expected structural rejection but graph is valid")
        continue

    if structurally_invalid:
        for e in schema_errors:
            fail(label, f"schema: {e.message}")
        for v in checker_violations:
            fail(label, f"checker: {v}")
        continue

    verdict, repair = gluing_verdict(data)

    if is_glue_inconclusive:
        if verdict != "INCONCLUSIVE" or repair is None:
            fail(label, f"expected INCONCLUSIVE gluing verdict with repair request, got {verdict}")
            continue
        # Determinism teeth: repair request must be content-addressable + stable.
        d1 = sha256_hex(canon(repair))
        d2 = sha256_hex(canon(gluing_verdict(data)[1]))
        if d1 != d2:
            fail(label, "repair request is non-deterministic (digests differ across runs)")
        else:
            ok(f"glue-inconclusive {label} (repair sha256:{d1[:12]})")
    else:
        if verdict != "GLUABLE":
            fail(label, f"expected GLUABLE gluing verdict, got {verdict}")
        else:
            ok(f"glue-ok {label}")

passed = sum(results)
if errors:
    print(file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"\n{passed} passed, {len(errors)} failed", file=sys.stderr)
    sys.exit(1)

print(f"\n{passed} evidence-cover-graph checks passed")
