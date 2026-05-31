#!/usr/bin/env python3
"""Validate Sprint-1 SCOPE-D hardening fixtures.

This is deliberately narrow. It enforces only the hardening doctrine needed
before broader ref/schema expansion:

1. PolicyFabric must not auto-approve SCOPE-D-derived work.
2. If an unsafe policy/placement trace appears anyway, receipt-style
   defense-in-depth must fail closed and require Void Network containment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "ops-fabric"

POLICY_FIXTURE = FIXTURE_DIR / "policyfabric-scope-d-auto-approval-denied.fixture.json"
VOID_FIXTURE = FIXTURE_DIR / "scope-d-derived-proposal-skips-human-review-routes-to-void.fixture.json"

ALLOWED_SCOPE_D_POLICY_OUTPUTS = {
    "DENIED",
    "ALLOWED_REPORT_ONLY",
    "REQUIRES_HUMAN_REVIEW_SCOPE_D_ACK",
}
UNSAFE_EVENT_TYPES = {
    "placement.selected",
    "run.started",
    "run.completed",
    "execution.lease.issued",
}
REQUIRED_HUMAN_REVIEW_SIGNAL = "human.reviewed.explicit_scope_d_ack"
REQUIRED_VOID_FORBIDDEN_ACTIONS = {
    "execute",
    "promote_to_canon",
    "write_to_memory_as_truth",
    "emit_execution_lease",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"missing fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_payloads(obj: Any):
    if isinstance(obj, dict):
        if "payload" in obj and isinstance(obj["payload"], dict):
            yield obj["payload"]
        yield obj
        for value in obj.values():
            yield from iter_payloads(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_payloads(item)


def contains_scope_d_provenance(obj: Any) -> bool:
    for payload in iter_payloads(obj):
        prov = payload.get("scope_d_provenance") if isinstance(payload, dict) else None
        if isinstance(prov, dict) and prov.get("derived_from_scope_d") is True:
            return True
    return False


def validate_policy_fixture() -> None:
    fx = load_json(POLICY_FIXTURE)

    if fx.get("expected_result") != "INVALID_POLICY_DECISION":
        raise AssertionError("policy fixture must expect INVALID_POLICY_DECISION")
    if fx.get("expected_reason") != "POLICY_CANNOT_AUTO_APPROVE_SCOPE_D_DERIVED":
        raise AssertionError("policy fixture has wrong expected_reason")

    input_prov = fx.get("input", {}).get("scope_d_provenance", {})
    if input_prov.get("derived_from_scope_d") is not True:
        raise AssertionError("policy fixture must start from SCOPE-D-derived input")

    invalid = fx.get("invalid_policy_output", {})
    if invalid.get("policy_status") != "ALLOWED_AUTO":
        raise AssertionError("policy fixture must cover ALLOWED_AUTO denial")
    if invalid.get("execution_eligible") is not True:
        raise AssertionError("policy fixture must cover execution_eligible denial")

    allowed = set(fx.get("allowed_policy_outputs", []))
    if allowed != ALLOWED_SCOPE_D_POLICY_OUTPUTS:
        raise AssertionError(
            "allowed policy outputs must be exactly "
            f"{sorted(ALLOWED_SCOPE_D_POLICY_OUTPUTS)}, got {sorted(allowed)}"
        )


def validate_void_fixture() -> None:
    fx = load_json(VOID_FIXTURE)

    expected = set(fx.get("expected_result", []))
    if expected != {"INVALID_FOR_EXECUTION", "ROUTED_TO_VOID_NETWORK"}:
        raise AssertionError("void fixture must expect invalid execution and void routing")
    if fx.get("expected_reason") != "SCOPE_D_DERIVED_PROPOSAL_MISSING_EXPLICIT_HUMAN_REVIEW_SEMAPHORE":
        raise AssertionError("void fixture has wrong expected_reason")

    trace = fx.get("trace", {})
    trace_id = trace.get("trace_id")
    events = trace.get("events", [])
    if not trace_id or not events:
        raise AssertionError("void fixture must include a trace_id and events")

    for event in events:
        if event.get("trace_id") != trace_id:
            raise AssertionError("all events must join on the fixture trace_id")

    event_types = [event.get("event_type") for event in events]
    if REQUIRED_HUMAN_REVIEW_SIGNAL in event_types:
        raise AssertionError("negative fixture must omit explicit human review semaphore")
    if not contains_scope_d_provenance(trace):
        raise AssertionError("void fixture must contain SCOPE-D provenance")

    unsafe_policy = False
    unsafe_transition = False
    for event in events:
        payload = event.get("payload", {})
        if event.get("event_type") == "policy.evaluated":
            if payload.get("policy_status") == "ALLOWED_AUTO" or payload.get("execution_eligible") is True:
                unsafe_policy = True
        if event.get("event_type") in UNSAFE_EVENT_TYPES:
            unsafe_transition = True

    if not unsafe_policy:
        raise AssertionError("void fixture must include unsafe policy output")
    if not unsafe_transition:
        raise AssertionError("void fixture must include unsafe downstream transition")

    void_record = fx.get("required_void_record", {})
    if void_record.get("void_reason") != "SCOPE_D_REQUIRES_HUMAN_REVIEW":
        raise AssertionError("void fixture must require SCOPE_D_REQUIRES_HUMAN_REVIEW")
    if void_record.get("containment_mode") != "REVIEW_QUEUE":
        raise AssertionError("void fixture must route to REVIEW_QUEUE")

    forbidden = set(void_record.get("forbidden_actions", []))
    missing = REQUIRED_VOID_FORBIDDEN_ACTIONS - forbidden
    if missing:
        raise AssertionError(f"void record missing forbidden actions: {sorted(missing)}")


def main() -> None:
    validate_policy_fixture()
    validate_void_fixture()
    print("[OK] SCOPE-D hardening fixtures validated")


if __name__ == "__main__":
    main()
