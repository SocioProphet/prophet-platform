#!/usr/bin/env python3
"""Validate WallGuard Professional Workroom product contract fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "wallguard" / "professional-workroom.example.json"

REQUIRED_TOP = {
    "schemaVersion",
    "recordType",
    "workroomRef",
    "clientRef",
    "matterRef",
    "wallRef",
    "policyRefs",
    "participants",
    "resourceRefs",
    "enforcementRefs",
    "requiredProductStates",
    "receiptRefs",
    "runtimeBoundary",
}

REQUIRED_PRODUCT_STATES = {
    "wall_state_visible",
    "policy_version_visible",
    "participant_membership_visible",
    "blocked_attempts_visible",
    "receipt_refs_visible",
    "clean_room_release_requestable",
}

REQUIRED_ENFORCEMENT_REFS = {
    "agentContext",
    "agentCollaboration",
    "guardrailBinding",
    "memoryGate",
    "retrievalFilter",
    "cleanRoomSynthesis",
}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing fixture: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        fail("fixture root must be an object")
    return data


def require_list(data: dict, key: str) -> list:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{key} must be a non-empty list")
    return value


def validate(data: dict) -> None:
    missing = sorted(REQUIRED_TOP - set(data))
    if missing:
        fail(f"missing top-level fields: {missing}")
    if data["schemaVersion"] != "prophet-platform.wallguard-professional-workroom.v0.1":
        fail("schemaVersion mismatch")
    if data["recordType"] != "WallGuardProfessionalWorkroom":
        fail("recordType mismatch")
    if not data["workroomRef"].startswith("workroom://"):
        fail("workroomRef must use workroom://")
    if not data["wallRef"].startswith("wall://"):
        fail("wallRef must use wall://")

    policy_refs = require_list(data, "policyRefs")
    if not any(ref.startswith("policy-fabric://") for ref in policy_refs):
        fail("policyRefs must include a Policy Fabric reference")

    participants = require_list(data, "participants")
    subject_types = {participant.get("subjectType") for participant in participants if isinstance(participant, dict)}
    if {"human", "agent"} - subject_types:
        fail("fixture must include at least one human and one agent participant")
    for participant in participants:
        if not isinstance(participant, dict):
            fail("participants must be objects")
        for key in ("subjectRef", "subjectType", "wallContextRef"):
            if not participant.get(key):
                fail(f"participant missing {key}")

    enforcement_refs = data["enforcementRefs"]
    if not isinstance(enforcement_refs, dict):
        fail("enforcementRefs must be an object")
    missing_refs = sorted(REQUIRED_ENFORCEMENT_REFS - set(enforcement_refs))
    if missing_refs:
        fail(f"missing enforcement refs: {missing_refs}")

    product_states = set(require_list(data, "requiredProductStates"))
    missing_states = sorted(REQUIRED_PRODUCT_STATES - product_states)
    if missing_states:
        fail(f"missing product states: {missing_states}")

    receipt_refs = require_list(data, "receiptRefs")
    if not all(str(ref).startswith("wallguard-receipt://") for ref in receipt_refs):
        fail("all receiptRefs must be wallguard-receipt:// refs")

    runtime = data["runtimeBoundary"]
    if not isinstance(runtime, dict):
        fail("runtimeBoundary must be an object")
    if runtime.get("policyAuthority") != "SocioProphet/policy-fabric":
        fail("policy authority must remain Policy Fabric")
    if runtime.get("productSurfaceOwner") != "SocioProphet/prophet-platform":
        fail("product surface owner must be Prophet Platform")
    if runtime.get("runtimeEnforcementImplemented") is not False:
        fail("this tranche must not claim runtime enforcement")


def main() -> int:
    try:
        validate(load_json(FIXTURE))
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("OK: WallGuard Professional Workroom fixture validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
