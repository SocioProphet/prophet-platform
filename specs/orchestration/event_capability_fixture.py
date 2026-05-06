#!/usr/bin/env python3
"""Canonical fixture and validator for event-based orchestration capabilities.

This is the event-driven layer above the Sovereign Device Orchestration and
E2WM trace contracts. It defines how observations become capability-gated,
policy-checked, idempotent, replayable reactions rather than opaque routines.

Run:
  python specs/orchestration/event_capability_fixture.py
  python specs/orchestration/event_capability_fixture.py --json
  python specs/orchestration/event_capability_fixture.py --events
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


EVENT_TYPES = {
    "sensor.threshold_crossed",
    "camera.semantic_event",
    "agent.plan_proposed",
    "policy.decision_emitted",
    "adapter.health_changed",
    "capability.reaction_scheduled",
    "capability.reaction_executed",
    "capability.dead_lettered",
}

EFFECT_CLASSES = {
    "observe",
    "explain",
    "search",
    "draft",
    "propose",
    "low_risk_actuation",
    "medium_risk_actuation",
    "high_risk_actuation",
    "irreversible_action",
}

POLICY_OUTCOMES = {
    "allowed",
    "denied",
    "requires_approval",
    "requires_local_only",
    "redacted",
    "degraded",
}

DELIVERY_MODES = {"at_least_once", "exactly_once_by_idempotency_key", "best_effort_observe_only"}


def fixture_bundle() -> dict[str, Any]:
    return {
        "contract_version": "sdo.event-capability.v0.1",
        "bundle_id": "bundle:fixture:event-capabilities:household:2026-05-06",
        "data_mode": "fixture",
        "related_contracts": [
            "sdo.v0.1",
            "e2wm.sdo.v0.1",
            "sourceos.orchestration.bundle.v0.1",
        ],
        "event_bus": {
            "bus_id": "bus:sourceos-local-orchestration",
            "delivery_mode": "exactly_once_by_idempotency_key",
            "dead_letter_topic": "orchestration.dead_letter.v0",
            "replay_topic": "orchestration.replay.v0",
            "audit_topic": "orchestration.audit.v0",
            "ordering_key_fields": ["subject_node_id", "capability_id"],
            "idempotency_key_fields": ["event_id", "capability_id", "target_node_id", "policy_epoch"],
        },
        "capabilities": [
            {
                "capability_id": "capability:observe-camera-semantic-event",
                "display_name": "Observe camera semantic event",
                "effect_class": "observe",
                "owner": "sourceos-syncd",
                "allowed_event_types": ["camera.semantic_event"],
                "target_node_types": ["camera"],
                "preconditions": ["adapter.health == healthy", "privacy.redaction_class != raw_video"],
                "postconditions": ["evidence_receipt.emitted == true", "raw_video_retained == false"],
                "required_policy_outcome": "redacted",
                "approval_mode": "none",
                "degraded_behavior": "metadata_only_receipt",
                "rate_limit": {"window_seconds": 60, "max_events": 120},
                "timeout_ms": 500,
            },
            {
                "capability_id": "capability:cool-room-with-fan",
                "display_name": "Cool room with fan when hot",
                "effect_class": "low_risk_actuation",
                "owner": "guardrail-fabric",
                "allowed_event_types": ["sensor.threshold_crossed"],
                "target_node_types": ["appliance"],
                "preconditions": ["temperature_f > 76", "occupancy == present", "target.trust_state == trusted"],
                "postconditions": ["fan.speed == medium", "evidence_receipt.emitted == true"],
                "required_policy_outcome": "allowed",
                "approval_mode": "notify",
                "degraded_behavior": "do_not_actuate_emit_degraded_receipt",
                "rate_limit": {"window_seconds": 300, "max_events": 3},
                "timeout_ms": 1500,
            },
            {
                "capability_id": "capability:arm-security-system",
                "display_name": "Arm household security system",
                "effect_class": "high_risk_actuation",
                "owner": "agentplane",
                "allowed_event_types": ["agent.plan_proposed"],
                "target_node_types": ["service"],
                "preconditions": ["target.policy_labels contains security", "approval.token.present == true"],
                "postconditions": ["security_system.state == armed", "evidence_receipt.emitted == true"],
                "required_policy_outcome": "requires_approval",
                "approval_mode": "explicit_user_approval",
                "degraded_behavior": "do_not_actuate_emit_degraded_receipt",
                "rate_limit": {"window_seconds": 3600, "max_events": 2},
                "timeout_ms": 2000,
            },
            {
                "capability_id": "capability:block-raw-camera-export",
                "display_name": "Block raw camera export",
                "effect_class": "high_risk_actuation",
                "owner": "guardrail-fabric",
                "allowed_event_types": ["agent.plan_proposed"],
                "target_node_types": ["camera"],
                "preconditions": ["requested_action == export_raw_video"],
                "postconditions": ["raw_video_exported == false", "denial_receipt.emitted == true"],
                "required_policy_outcome": "denied",
                "approval_mode": "not_overridable_in_first_slice",
                "degraded_behavior": "deny_closed",
                "rate_limit": {"window_seconds": 3600, "max_events": 1000},
                "timeout_ms": 300,
            },
        ],
        "subscriptions": [
            subscription("subscription:camera-semantic-events", "camera.semantic_event", "capability:observe-camera-semantic-event", "node:front-door-camera-01"),
            subscription("subscription:temperature-to-fan", "sensor.threshold_crossed", "capability:cool-room-with-fan", "node:living-room-fan-01"),
            subscription("subscription:security-plan-review", "agent.plan_proposed", "capability:arm-security-system", "node:security-system-01"),
            subscription("subscription:raw-camera-export-denial", "agent.plan_proposed", "capability:block-raw-camera-export", "node:front-door-camera-01"),
        ],
        "events": [
            event(
                "event:sensor:living-room-temp-high",
                "sensor.threshold_crossed",
                "node:living-room-temp-01",
                "node:living-room-fan-01",
                payload={"metric": "temperature_f", "value": 78.4, "operator": ">", "threshold": 76, "occupancy": "present"},
                idempotency_key="idem:event:sensor:living-room-temp-high:capability:cool-room-with-fan:node:living-room-fan-01:policy-epoch-0",
            ),
            event(
                "event:camera:package-delivered",
                "camera.semantic_event",
                "node:front-door-camera-01",
                "node:front-door-camera-01",
                payload={"summary": "package delivered", "raw_video_retained": False, "redaction_class": "metadata_only"},
                idempotency_key="idem:event:camera:package-delivered:capability:observe-camera-semantic-event:node:front-door-camera-01:policy-epoch-0",
            ),
            event(
                "event:agent:propose-arm-security",
                "agent.plan_proposed",
                "node:agent-household-orchestrator",
                "node:security-system-01",
                payload={"requested_action": "arm_alarm", "approval_token_present": False, "capability_class": "high_risk_actuation"},
                idempotency_key="idem:event:agent:propose-arm-security:capability:arm-security-system:node:security-system-01:policy-epoch-0",
            ),
            event(
                "event:agent:request-raw-camera-export",
                "agent.plan_proposed",
                "node:agent-household-orchestrator",
                "node:front-door-camera-01",
                payload={"requested_action": "export_raw_video", "capability_class": "high_risk_actuation"},
                idempotency_key="idem:event:agent:request-raw-camera-export:capability:block-raw-camera-export:node:front-door-camera-01:policy-epoch-0",
            ),
        ],
        "reaction_plans": [
            reaction("reaction:cool-room-with-fan", "event:sensor:living-room-temp-high", "capability:cool-room-with-fan", "allowed", ["receipt:event:living-room-temp-high", "receipt:policy:allow-cool-living-room"]),
            reaction("reaction:observe-package-delivery", "event:camera:package-delivered", "capability:observe-camera-semantic-event", "redacted", ["receipt:event:package-delivered"]),
            reaction("reaction:security-arm-needs-approval", "event:agent:propose-arm-security", "capability:arm-security-system", "requires_approval", ["receipt:agent:propose-arm-security", "receipt:policy:requires-approval-arm-security"]),
            reaction("reaction:block-raw-camera-export", "event:agent:request-raw-camera-export", "capability:block-raw-camera-export", "denied", ["receipt:policy:deny-raw-camera-export"]),
        ],
        "world_class_invariants": [
            "every_reaction_has_idempotency_key",
            "every_capability_declares_effect_class",
            "high_risk_capabilities_require_approval_or_denial",
            "raw_camera_export_denied_by_default",
            "every_reaction_emits_or_references_evidence_receipts",
            "degraded_adapters_do_not_actuate",
            "dead_letter_route_declared",
            "replay_topic_declared",
        ],
    }


def subscription(subscription_id: str, event_type: str, capability_id: str, target_node_id: str) -> dict[str, Any]:
    return {
        "subscription_id": subscription_id,
        "event_type": event_type,
        "capability_id": capability_id,
        "target_node_id": target_node_id,
        "enabled": True,
        "filter": {"data_mode": "fixture"},
        "delivery_mode": "exactly_once_by_idempotency_key",
    }


def event(event_id: str, event_type: str, actor_id: str, target_node_id: str, *, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-05-06T12:00:00Z",
        "actor_id": actor_id,
        "target_node_id": target_node_id,
        "payload": payload,
        "causality": {
            "trace_id": "trace:event-capability:fixture",
            "parent_event_ids": [],
            "idempotency_key": idempotency_key,
            "policy_epoch": "policy-epoch-0",
        },
    }


def reaction(reaction_id: str, event_id: str, capability_id: str, policy_outcome: str, receipt_refs: list[str]) -> dict[str, Any]:
    return {
        "reaction_id": reaction_id,
        "event_id": event_id,
        "capability_id": capability_id,
        "policy_outcome": policy_outcome,
        "status": "scheduled" if policy_outcome in {"allowed", "redacted"} else "blocked_or_waiting",
        "receipt_refs": receipt_refs,
        "scheduled_at": "2026-05-06T12:00:01Z",
        "retry": {"max_attempts": 1, "backoff_ms": 0},
        "dead_letter_on_failure": True,
    }


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bundle.get("contract_version") != "sdo.event-capability.v0.1":
        errors.append("contract_version must be sdo.event-capability.v0.1")
    if bundle.get("data_mode") != "fixture":
        errors.append("data_mode must be fixture")

    event_bus = bundle.get("event_bus", {})
    if event_bus.get("delivery_mode") not in DELIVERY_MODES:
        errors.append("event_bus.delivery_mode is invalid")
    for required in ("dead_letter_topic", "replay_topic", "audit_topic"):
        if not event_bus.get(required):
            errors.append("event_bus missing " + required)
    if not event_bus.get("idempotency_key_fields"):
        errors.append("event_bus must declare idempotency_key_fields")

    caps = {cap.get("capability_id"): cap for cap in bundle.get("capabilities", [])}
    subs = {sub.get("subscription_id"): sub for sub in bundle.get("subscriptions", [])}
    events = {evt.get("event_id"): evt for evt in bundle.get("events", [])}
    reactions = {rxn.get("reaction_id"): rxn for rxn in bundle.get("reaction_plans", [])}

    for name, values in (("capability", caps), ("subscription", subs), ("event", events), ("reaction", reactions)):
        if None in values or "" in values:
            errors.append(name + " missing id")

    for cap_id, cap in caps.items():
        if cap.get("effect_class") not in EFFECT_CLASSES:
            errors.append(str(cap_id) + ": invalid effect_class")
        if cap.get("required_policy_outcome") not in POLICY_OUTCOMES:
            errors.append(str(cap_id) + ": invalid required_policy_outcome")
        for event_type in cap.get("allowed_event_types", []):
            if event_type not in EVENT_TYPES:
                errors.append(str(cap_id) + ": invalid allowed_event_type " + str(event_type))
        if cap.get("effect_class") in {"high_risk_actuation", "irreversible_action"}:
            if cap.get("approval_mode") not in {"explicit_user_approval", "two_party_approval", "admin_approval", "not_overridable_in_first_slice"}:
                errors.append(str(cap_id) + ": high-risk capability lacks strict approval/denial mode")
        if cap.get("display_name", "").lower().find("raw camera") >= 0 and cap.get("required_policy_outcome") != "denied":
            errors.append(str(cap_id) + ": raw camera export must be denied by default")
        if not cap.get("degraded_behavior"):
            errors.append(str(cap_id) + ": missing degraded_behavior")

    for sub_id, sub in subs.items():
        if sub.get("event_type") not in EVENT_TYPES:
            errors.append(str(sub_id) + ": invalid event_type")
        if sub.get("capability_id") not in caps:
            errors.append(str(sub_id) + ": unknown capability_id")
        cap = caps.get(sub.get("capability_id"), {})
        if sub.get("event_type") not in cap.get("allowed_event_types", []):
            errors.append(str(sub_id) + ": event_type not allowed by capability")
        if sub.get("delivery_mode") not in DELIVERY_MODES:
            errors.append(str(sub_id) + ": invalid delivery_mode")

    for event_id, evt in events.items():
        if evt.get("event_type") not in EVENT_TYPES:
            errors.append(str(event_id) + ": invalid event_type")
        causality = evt.get("causality", {})
        if not causality.get("idempotency_key"):
            errors.append(str(event_id) + ": missing idempotency key")
        if not causality.get("trace_id"):
            errors.append(str(event_id) + ": missing trace_id")
        if not causality.get("policy_epoch"):
            errors.append(str(event_id) + ": missing policy_epoch")

    for reaction_id, rxn in reactions.items():
        if rxn.get("event_id") not in events:
            errors.append(str(reaction_id) + ": unknown event_id")
        if rxn.get("capability_id") not in caps:
            errors.append(str(reaction_id) + ": unknown capability_id")
        if rxn.get("policy_outcome") not in POLICY_OUTCOMES:
            errors.append(str(reaction_id) + ": invalid policy_outcome")
        cap = caps.get(rxn.get("capability_id"), {})
        if cap and rxn.get("policy_outcome") != cap.get("required_policy_outcome"):
            errors.append(str(reaction_id) + ": reaction policy_outcome does not match capability required_policy_outcome")
        if not rxn.get("receipt_refs"):
            errors.append(str(reaction_id) + ": missing receipt_refs")
        if rxn.get("dead_letter_on_failure") is not True:
            errors.append(str(reaction_id) + ": dead_letter_on_failure must be true")

    invariants = set(bundle.get("world_class_invariants", []))
    for invariant in (
        "every_reaction_has_idempotency_key",
        "high_risk_capabilities_require_approval_or_denial",
        "raw_camera_export_denied_by_default",
        "every_reaction_emits_or_references_evidence_receipts",
        "dead_letter_route_declared",
        "replay_topic_declared",
    ):
        if invariant not in invariants:
            errors.append("missing invariant: " + invariant)

    return errors


def event_records(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    caps = {cap["capability_id"]: cap for cap in bundle["capabilities"]}
    events = {evt["event_id"]: evt for evt in bundle["events"]}
    records = []
    for rxn in bundle["reaction_plans"]:
        cap = caps[rxn["capability_id"]]
        evt = events[rxn["event_id"]]
        records.append(
            {
                "record_id": "record:" + rxn["reaction_id"].split(":", 1)[1],
                "mode": "event-capability-evidence-v0",
                "event": evt,
                "capability": cap,
                "reaction": rxn,
                "evidence_refs": rxn["receipt_refs"],
                "search_text": " ".join(
                    [
                        str(evt["event_type"]),
                        str(cap["display_name"]),
                        str(cap["effect_class"]),
                        str(rxn["policy_outcome"]),
                        json.dumps(evt.get("payload", {}), sort_keys=True),
                    ]
                ),
            }
        )
    return records


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit full event-capability bundle")
    parser.add_argument("--events", action="store_true", help="emit flattened event-capability records")
    args = parser.parse_args(argv)

    bundle = fixture_bundle()
    errors = validate_bundle(bundle)

    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0 if not errors else 1
    if args.events:
        print(json.dumps(event_records(bundle), indent=2, sort_keys=True))
        return 0 if not errors else 1

    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1

    print("event capability validation passed")
    print("capabilities={} subscriptions={} events={} reactions={}".format(len(bundle["capabilities"]), len(bundle["subscriptions"]), len(bundle["events"]), len(bundle["reaction_plans"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
