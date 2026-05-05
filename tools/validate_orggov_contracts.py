#!/usr/bin/env python3
"""Validate Organization Governance Control Plane v0 contracts."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "orggov.manifest.yaml"
SCHEMA = ROOT / "contracts/orggov/orggov-control-plane.v0.1.schema.json"
EXAMPLE = ROOT / "contracts/orggov/orggov-control-plane.v0.1.example.json"


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def check_manifest() -> None:
    if not MANIFEST.exists():
        fail("missing orggov.manifest.yaml")
    paths = re.findall(r"^\s*-\s+(contracts/[^\s#]+)\s*$", MANIFEST.read_text(encoding="utf-8"), re.M)
    if not paths:
        fail("manifest does not declare contractPaths")
    missing = [path for path in paths if not (ROOT / path).exists()]
    if missing:
        fail("manifest references missing contract paths: " + ", ".join(missing))
    print(f"ok: manifest references {len(paths)} existing contract paths")


def item_ids(record: dict, key: str) -> set[str]:
    items = record.get(key)
    if not isinstance(items, list) or not items:
        fail(f"{key}: expected non-empty list")
    result = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or "id" not in item:
            fail(f"{key}[{index}]: missing id")
        result.add(item["id"])
    return result


def require_ref(ref: str, known: set[str], label: str) -> None:
    if ref not in known:
        fail(f"{label}: unknown ref {ref!r}")


def require_refs(refs: list[str], known: set[str], label: str) -> None:
    if not isinstance(refs, list):
        fail(f"{label}: expected list")
    for ref in refs:
        require_ref(ref, known, label)


def main() -> int:
    schema = load_json(SCHEMA)
    record = load_json(EXAMPLE)
    check_manifest()

    required = schema.get("required", [])
    missing = [key for key in required if key not in record]
    if missing:
        fail("example missing required top-level keys: " + ", ".join(missing))
    if record.get("schemaVersion") != "orggov.control-plane.v0.1":
        fail("schemaVersion must be orggov.control-plane.v0.1")
    if record.get("recordType") != "OrgGovControlPlaneRecord":
        fail("recordType must be OrgGovControlPlaneRecord")

    objective_id = record["objective"]["id"]
    workroom_id = record["workroom"]["id"]
    work_order_id = record["workOrder"]["id"]

    actor_ids = item_ids(record, "actors")
    asset_ids = item_ids(record, "assets")
    policy_ids = item_ids(record, "policyDecisions")
    action_ids = item_ids(record, "actions")
    evidence_ids = item_ids(record, "evidence")
    review_ids = item_ids(record, "reviews")
    outcome_ids = item_ids(record, "outcomes")
    all_ids = {objective_id, workroom_id, work_order_id} | actor_ids | asset_ids | policy_ids | action_ids | evidence_ids | review_ids | outcome_ids | item_ids(record, "roleBindings") | item_ids(record, "scores") | item_ids(record, "learningEvents")

    require_ref(record["objective"]["ownerRef"], actor_ids, "objective.ownerRef")
    require_ref(record["workOrder"]["objectiveRef"], {objective_id}, "workOrder.objectiveRef")
    require_ref(record["workOrder"]["workroomRef"], {workroom_id}, "workOrder.workroomRef")

    for binding in record["roleBindings"]:
        require_ref(binding["actorRef"], actor_ids, f"{binding['id']}.actorRef")
        require_refs(binding["scopeRefs"], all_ids, f"{binding['id']}.scopeRefs")
    for decision in record["policyDecisions"]:
        require_ref(decision["actorRef"], actor_ids, f"{decision['id']}.actorRef")
        require_ref(decision["actionRef"], action_ids, f"{decision['id']}.actionRef")
        require_refs(decision["assetRefs"], asset_ids, f"{decision['id']}.assetRefs")
    for action in record["actions"]:
        require_ref(action["actorRef"], actor_ids, f"{action['id']}.actorRef")
        require_refs(action["targetAssetRefs"], asset_ids, f"{action['id']}.targetAssetRefs")
        require_refs(action["policyDecisionRefs"], policy_ids, f"{action['id']}.policyDecisionRefs")
        require_refs(action["evidenceRefs"], evidence_ids, f"{action['id']}.evidenceRefs")
    for evidence in record["evidence"]:
        require_refs(evidence["supportsRefs"], all_ids, f"{evidence['id']}.supportsRefs")
    for review in record["reviews"]:
        require_ref(review["reviewerRef"], actor_ids, f"{review['id']}.reviewerRef")
        require_refs(review["subjectRefs"], all_ids, f"{review['id']}.subjectRefs")
    for outcome in record["outcomes"]:
        require_refs(outcome["reviewRefs"], review_ids, f"{outcome['id']}.reviewRefs")
        require_refs(outcome["evidenceRefs"], evidence_ids, f"{outcome['id']}.evidenceRefs")
    for score in record["scores"]:
        require_ref(score["outcomeRef"], outcome_ids, f"{score['id']}.outcomeRef")
    for learning in record["learningEvents"]:
        require_ref(learning["triggerRef"], all_ids, f"{learning['id']}.triggerRef")
        require_refs(learning["appliesToRefs"], all_ids, f"{learning['id']}.appliesToRefs")

    if record["provenance"].get("nonSecret") is not True:
        fail("provenance.nonSecret must be true for committed fixtures")
    print("OK: Organization Governance Control Plane validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
