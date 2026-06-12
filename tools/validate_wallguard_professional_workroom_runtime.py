#!/usr/bin/env python3
"""
Validates WallGuard Professional Workroom runtime-state fixtures.

Policy gates enforced:
  - wall_ref must be present and non-null (fail closed on missing wall context)
  - blocked_attempts must not embed restricted_payload_embedded=true
  - runtime_boundary.runtime_enforcement_implemented must be false
  - clean_room_release_request (when present) must reference policy_decision_ref,
    holmes_evidence_ref, and core_ledger_evidence_ref
  - non_claims must be non-empty
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "wallguard"

REQUIRED_FIELDS = {
    "kind",
    "schema_version",
    "workroom_ref",
    "client_ref",
    "matter_ref",
    "wall_ref",
    "wall_state",
    "policy_version",
    "participants",
    "blocked_attempts",
    "receipt_refs",
    "enforcement_refs",
    "runtime_boundary",
    "non_claims",
}

REQUIRED_ENFORCEMENT_REFS = {
    "agent_context",
    "agent_collaboration",
    "guardrail_binding",
    "memory_gate",
    "retrieval_filter",
    "clean_room_synthesis",
}

VALID_WALL_STATES = {"active", "suspended", "dissolved"}
VALID_ATTEMPT_TYPES = {
    "cross_wall_retrieval",
    "cross_wall_writeback",
    "cross_wall_collaboration",
}


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root must be object")
    return data


def check_policy_gates(data: dict) -> list[str]:
    problems: list[str] = []

    if data.get("kind") != "WallGuardProfessionalWorkroomRuntimeState":
        problems.append(f"kind must be WallGuardProfessionalWorkroomRuntimeState, got {data.get('kind')!r}")

    if data.get("schema_version") != "wallguard-professional-workroom-runtime-state.v0.1":
        problems.append("schema_version mismatch")

    missing = sorted(REQUIRED_FIELDS - set(data))
    if missing:
        problems.append(f"missing required fields: {missing}")
        return problems

    # Fail closed on missing wall context
    if not data.get("wall_ref"):
        problems.append("wall_ref is required — must fail closed when wall context is absent")

    wall_state = data.get("wall_state")
    if wall_state not in VALID_WALL_STATES:
        problems.append(f"wall_state must be one of {sorted(VALID_WALL_STATES)}, got {wall_state!r}")

    if not str(data.get("policy_version", "")).startswith("policy-fabric://"):
        problems.append("policy_version must reference a Policy Fabric policy")

    # Participants: at least one human and one agent
    participants = data.get("participants", [])
    if not isinstance(participants, list) or not participants:
        problems.append("participants must be a non-empty list")
    else:
        types = {p.get("subject_type") for p in participants if isinstance(p, dict)}
        if "human" not in types or "agent" not in types:
            problems.append("participants must include at least one human and one agent")
        for p in participants:
            if not isinstance(p, dict):
                continue
            for key in ("subject_ref", "subject_type", "wall_context_ref", "acknowledgment_state"):
                if not p.get(key):
                    problems.append(f"participant missing {key}")

    # Blocked attempts — no restricted payload embedded
    blocked = data.get("blocked_attempts", [])
    if not isinstance(blocked, list):
        problems.append("blocked_attempts must be a list")
    else:
        for attempt in blocked:
            if not isinstance(attempt, dict):
                continue
            if attempt.get("restricted_payload_embedded") is True:
                problems.append(
                    "blocked attempt must not embed restricted payload content "
                    f"(attempt_type={attempt.get('attempt_type')!r}, subject={attempt.get('subject_ref')!r})"
                )
            if attempt.get("attempt_type") not in VALID_ATTEMPT_TYPES:
                problems.append(f"unknown attempt_type: {attempt.get('attempt_type')!r}")
            if not attempt.get("receipt_ref", "").startswith("wallguard-receipt://"):
                problems.append("blocked attempt receipt_ref must use wallguard-receipt://")
            if not attempt.get("policy_decision_ref", "").startswith("policy-fabric://"):
                problems.append("blocked attempt policy_decision_ref must reference Policy Fabric")

    # Enforcement refs
    enforcement = data.get("enforcement_refs", {})
    if not isinstance(enforcement, dict):
        problems.append("enforcement_refs must be an object")
    else:
        missing_refs = sorted(REQUIRED_ENFORCEMENT_REFS - set(enforcement))
        if missing_refs:
            problems.append(f"missing enforcement_refs: {missing_refs}")

    # Runtime boundary — must not claim enforcement
    boundary = data.get("runtime_boundary", {})
    if not isinstance(boundary, dict):
        problems.append("runtime_boundary must be an object")
    else:
        if boundary.get("policy_authority") != "SocioProphet/policy-fabric":
            problems.append("runtime_boundary.policy_authority must be SocioProphet/policy-fabric")
        if boundary.get("runtime_enforcement_implemented") is not False:
            problems.append(
                "runtime_boundary.runtime_enforcement_implemented must be false "
                "(product surface must not claim policy authority)"
            )

    # Clean-room release request evidence completeness
    clean_room = data.get("clean_room_release_request")
    if clean_room is not None:
        if not isinstance(clean_room, dict):
            problems.append("clean_room_release_request must be an object")
        else:
            for ref_key in ("policy_decision_ref", "holmes_evidence_ref", "core_ledger_evidence_ref"):
                if not clean_room.get(ref_key):
                    problems.append(f"clean_room_release_request missing {ref_key}")
            if not clean_room.get("non_claims"):
                problems.append("clean_room_release_request must include non_claims")

    # Top-level non_claims
    if not data.get("non_claims"):
        problems.append("non_claims must be non-empty")

    return problems


def validate_file(path: Path) -> list[str]:
    try:
        data = load_json(path)
    except Exception as exc:
        return [f"parse error: {exc}"]
    return check_policy_gates(data)


def ok(label: str) -> None:
    print(f"ok: {label}")


def fail(label: str, problems: list[str]) -> None:
    print(f"FAIL: {label}")
    for p in problems:
        print(f"  - {p}")


def main() -> int:
    valids = sorted(CONTRACT_DIR.glob("professional-workroom-runtime-state*.json"))
    rejects = sorted(CONTRACT_DIR.glob("reject.*.json"))

    if not valids:
        raise SystemExit("no valid wallguard runtime-state fixtures found")
    if not rejects:
        raise SystemExit("no reject wallguard fixtures found")

    failed = False

    for path in valids:
        problems = validate_file(path)
        if problems:
            fail(path.name, problems)
            failed = True
        else:
            ok(path.name)

    for path in rejects:
        problems = validate_file(path)
        if not problems:
            print(f"FAIL (reject should have failed): {path.name}")
            failed = True
        else:
            ok(f"(rejected as expected): {path.name}")

    print(
        ("PASS" if not failed else "FAIL")
        + f": wallguard professional workroom runtime — {len(valids)} valid, {len(rejects)} reject"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
