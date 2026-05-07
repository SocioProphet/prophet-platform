#!/usr/bin/env python3
"""Generate the world-class event-native orchestration demo bundle.

This script ties together the current bootstrap contracts without requiring
live Apple, Google, Samsung, Amazon, Home Assistant, SourceOS, AgentPlane,
Sherlock, or Guardrail credentials.

It proves the local fixture chain:

  core contract -> embodied traces -> event capabilities -> policy annotation
  -> SourceOS queue projection -> AgentPlane admission artifact -> Sherlock index

Run:
  python specs/orchestration/world_class_event_loop_demo.py
  python specs/orchestration/world_class_event_loop_demo.py --out /tmp/sdo-demo --compact
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import embodied_experience_trace_fixture as e2wm
import event_capability_fixture as eventcap
import orchestration_contract_fixture as sdo


HIGH_RISK_EFFECTS = {"high_risk_actuation", "irreversible_action"}
EXECUTABLE_OUTCOMES = {"allowed", "redacted"}
WAITING_OUTCOMES = {"requires_approval"}
BLOCKING_OUTCOMES = {"denied", "degraded", "requires_local_only"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def event_records_from_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return eventcap.event_records(bundle)


def evaluate_policy(record: dict[str, Any]) -> dict[str, Any]:
    event = record.get("event") if isinstance(record.get("event"), dict) else {}
    capability = record.get("capability") if isinstance(record.get("capability"), dict) else {}
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}

    action = str(payload.get("requested_action") or capability.get("capability_id") or "observe")
    event_type = str(event.get("event_type", ""))
    effect_class = str(capability.get("effect_class", "observe"))
    adapter_health = str(payload.get("adapter_health", capability.get("adapter_health", "healthy")))
    approval_mode = str(capability.get("approval_mode", "none"))
    capability_id = str(capability.get("capability_id", "unknown"))

    reasons: list[str] = []
    outcome = "allowed"

    if adapter_health in {"degraded", "disabled", "unavailable"}:
        outcome = "degraded"
        reasons.append("Adapter is degraded or unavailable; action is non-executable until repair/replay.")
    elif event_type == "camera.semantic_event" and effect_class == "observe":
        outcome = "redacted"
        reasons.append("Camera semantic observation is allowed only as redacted metadata in the bootstrap lane.")
    elif "camera-media-release" in capability_id or "media_release" in action or "export" in action:
        outcome = "denied"
        reasons.append("Camera media release is denied by default in the first orchestration slice.")
    elif effect_class in HIGH_RISK_EFFECTS:
        if approval_mode in {"explicit_user_approval", "two_party_approval", "admin_approval"}:
            outcome = "requires_approval"
            reasons.append("High-risk event capability requires explicit approval before execution.")
        else:
            outcome = "denied"
            reasons.append("High-risk event capability lacks strict approval mode.")
    elif effect_class == "medium_risk_actuation":
        outcome = "requires_approval"
        reasons.append("Medium-risk event capability requires approval in the bootstrap policy.")
    elif effect_class == "low_risk_actuation":
        outcome = "allowed"
        reasons.append("Low-risk actuation is allowed when preconditions and trust state are valid.")
    elif effect_class in {"observe", "explain", "search", "draft", "propose"}:
        outcome = "allowed"
        reasons.append("Non-actuating capability is allowed with receipt emission.")
    else:
        outcome = "denied"
        reasons.append("Unknown effect class denied fail-closed.")

    return {
        "decision_id": "decision:event-capability:" + str(record.get("record_id", "unknown")).replace("record:", ""),
        "outcome": outcome,
        "evaluated_at": utc_now(),
        "actor_id": "adapter:guardrail-fabric-fixture",
        "subject_node_id": str(event.get("target_node_id", "unknown")),
        "event_id": str(event.get("event_id", "event:unknown")),
        "capability_class": effect_class,
        "policy_package": str(capability.get("policy_package", "guardrail-fabric/device-orchestration@0.1")),
        "reasons": reasons,
    }


def annotate_policy(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for record in records:
        item = deepcopy(record)
        decision = evaluate_policy(item)
        reaction = item.get("reaction") if isinstance(item.get("reaction"), dict) else {}
        capability = item.get("capability") if isinstance(item.get("capability"), dict) else {}
        reaction["policy_outcome"] = decision["outcome"]
        reaction["status"] = "scheduled" if decision["outcome"] in EXECUTABLE_OUTCOMES else "blocked_or_waiting"
        reaction["dead_letter_on_failure"] = True
        reaction.setdefault("receipt_refs", [])
        capability["required_policy_outcome"] = decision["outcome"]
        item["reaction"] = reaction
        item["capability"] = capability
        item["policy_decision"] = decision
        item["evidence_refs"] = sorted(set((item.get("evidence_refs") or []) + reaction.get("receipt_refs", [])))
        annotated.append(item)
    return annotated


def admission_for_record(record: dict[str, Any]) -> dict[str, Any]:
    event = record.get("event") if isinstance(record.get("event"), dict) else {}
    capability = record.get("capability") if isinstance(record.get("capability"), dict) else {}
    reaction = record.get("reaction") if isinstance(record.get("reaction"), dict) else {}
    causality = event.get("causality") if isinstance(event.get("causality"), dict) else {}

    errors: list[str] = []
    warnings: list[str] = []
    effect_class = str(capability.get("effect_class", ""))
    policy_outcome = str(reaction.get("policy_outcome", ""))
    idempotency_key = str(causality.get("idempotency_key", ""))
    receipt_refs = record.get("evidence_refs") or reaction.get("receipt_refs") or []

    if not event.get("event_id"):
        errors.append("missing event_id")
    if not capability.get("capability_id"):
        errors.append("missing capability_id")
    if not idempotency_key:
        errors.append("missing idempotency key")
    if not receipt_refs:
        errors.append("missing evidence receipt references")
    if reaction.get("dead_letter_on_failure") is not True:
        errors.append("dead_letter_on_failure must be true")
    if policy_outcome != capability.get("required_policy_outcome"):
        errors.append("policy outcome does not match capability required_policy_outcome")

    if effect_class in HIGH_RISK_EFFECTS:
        approval_mode = str(capability.get("approval_mode", ""))
        if policy_outcome == "allowed":
            errors.append("high-risk capability cannot be directly allowed in bootstrap admission")
        if policy_outcome == "requires_approval" and approval_mode not in {"explicit_user_approval", "two_party_approval", "admin_approval"}:
            errors.append("high-risk approval outcome lacks strict approval mode")
        if policy_outcome == "denied":
            warnings.append("high-risk capability denied; preserve denial receipt for replay")

    if policy_outcome in EXECUTABLE_OUTCOMES and not errors:
        admission = "admitted"
    elif policy_outcome in WAITING_OUTCOMES and not errors:
        admission = "waiting_for_approval"
    elif policy_outcome in BLOCKING_OUTCOMES and not errors:
        admission = "blocked"
    else:
        admission = "invalid"

    return {
        "record_id": record.get("record_id"),
        "event_id": event.get("event_id"),
        "capability_id": capability.get("capability_id"),
        "effect_class": effect_class,
        "policy_outcome": policy_outcome,
        "idempotency_key": idempotency_key,
        "receipt_refs": receipt_refs,
        "admission": admission,
        "errors": errors,
        "warnings": warnings,
    }


def admission_artifact(records: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = [admission_for_record(record) for record in records]
    return {
        "schema": "agentplane.event_capability_admission.v0.1",
        "artifactId": str(uuid4()),
        "timestamp": utc_now(),
        "summary": {
            "total": len(decisions),
            "admitted": sum(1 for item in decisions if item["admission"] == "admitted"),
            "waiting_for_approval": sum(1 for item in decisions if item["admission"] == "waiting_for_approval"),
            "blocked": sum(1 for item in decisions if item["admission"] == "blocked"),
            "invalid": sum(1 for item in decisions if item["admission"] == "invalid"),
        },
        "agentMayExecute": all(item["admission"] != "invalid" for item in decisions),
        "decisions": decisions,
    }


def sourceos_queue_snapshot(records: list[dict[str, Any]], admission: dict[str, Any]) -> dict[str, Any]:
    queue = {"pending": [], "waiting-approval": [], "blocked": [], "dead-letter": []}
    decisions_by_record = {item["record_id"]: item for item in admission["decisions"]}
    for record in records:
        decision = decisions_by_record.get(record.get("record_id"), {})
        admission_state = decision.get("admission", "invalid")
        if admission_state == "admitted":
            state = "pending"
        elif admission_state == "waiting_for_approval":
            state = "waiting-approval"
        elif admission_state == "blocked":
            state = "blocked"
        else:
            state = "dead-letter"
        queue[state].append(
            {
                "record_id": record.get("record_id"),
                "event_id": decision.get("event_id"),
                "capability_id": decision.get("capability_id"),
                "policy_outcome": decision.get("policy_outcome"),
                "idempotency_key": decision.get("idempotency_key"),
                "receipt_refs": decision.get("receipt_refs", []),
            }
        )
    return {
        "schema": "sourceos.orchestration.event-queue.v0.1",
        "created_at": utc_now(),
        "delivery_mode": "exactly_once_by_idempotency_key",
        "non_mutating": True,
        "counts": {state: len(items) for state, items in queue.items()},
        "queue": queue,
        "replay": {
            "schema": "sourceos.orchestration.replay.v0.1",
            "source_state": "pending",
            "count": len(queue["pending"]),
            "records": queue["pending"],
            "non_mutating": True,
        },
    }


def sherlock_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    indexed = []
    for record in records:
        event = record.get("event", {})
        capability = record.get("capability", {})
        reaction = record.get("reaction", {})
        causality = event.get("causality", {}) if isinstance(event.get("causality"), dict) else {}
        indexed.append(
            {
                "record_id": record.get("record_id"),
                "mode": "event-capability-evidence-v0",
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "capability_id": capability.get("capability_id"),
                "capability_name": capability.get("display_name"),
                "effect_class": capability.get("effect_class"),
                "policy_outcome": reaction.get("policy_outcome"),
                "reaction_id": reaction.get("reaction_id"),
                "idempotency_key": causality.get("idempotency_key"),
                "policy_epoch": causality.get("policy_epoch"),
                "receipt_refs": record.get("evidence_refs", []),
                "search_text": " ".join(
                    [
                        str(event.get("event_type", "")),
                        str(capability.get("display_name", "")),
                        str(capability.get("effect_class", "")),
                        str(reaction.get("policy_outcome", "")),
                        json.dumps(event.get("payload", {}), sort_keys=True),
                    ]
                ),
            }
        )
    return {
        "schema": "sherlock.event-capability-index.v0.1",
        "created_at": utc_now(),
        "source_authority": "Prophet Platform world-class event loop demo",
        "record_count": len(indexed),
        "records": indexed,
    }


def demo_report(
    core_errors: list[str],
    trace_errors: list[str],
    event_errors: list[str],
    records: list[dict[str, Any]],
    admission: dict[str, Any],
    queue: dict[str, Any],
    sherlock: dict[str, Any],
) -> dict[str, Any]:
    high_risk_direct_allow = [
        record.get("record_id")
        for record in records
        if (record.get("capability", {}).get("effect_class") in HIGH_RISK_EFFECTS)
        and record.get("reaction", {}).get("policy_outcome") == "allowed"
    ]
    camera_media_release_not_denied = [
        record.get("record_id")
        for record in records
        if "camera-media-release" in str(record.get("capability", {}).get("capability_id", ""))
        and record.get("reaction", {}).get("policy_outcome") != "denied"
    ]
    no_idempotency = [item["record_id"] for item in admission["decisions"] if not item.get("idempotency_key")]
    no_receipts = [item["record_id"] for item in admission["decisions"] if not item.get("receipt_refs")]

    invariants = {
        "core_contract_valid": not core_errors,
        "embodied_trace_valid": not trace_errors,
        "event_capability_valid": not event_errors,
        "no_high_risk_direct_allow": not high_risk_direct_allow,
        "camera_media_release_denied_by_default": not camera_media_release_not_denied,
        "every_reaction_has_idempotency_key": not no_idempotency,
        "every_reaction_has_receipt_refs": not no_receipts,
        "agentplane_no_invalid_admissions": admission["summary"]["invalid"] == 0,
        "sourceos_has_pending_waiting_and_blocked_states": all(queue["counts"].get(state, 0) > 0 for state in ("pending", "waiting-approval", "blocked")),
        "sourceos_replay_is_non_mutating": queue["replay"]["non_mutating"] is True,
        "sherlock_index_covers_all_records": sherlock["record_count"] == len(records),
    }
    return {
        "schema": "sdo.world-class-event-loop-demo.v0.1",
        "created_at": utc_now(),
        "status": "pass" if all(invariants.values()) else "fail",
        "summary": {
            "records": len(records),
            "admission": admission["summary"],
            "queue_counts": queue["counts"],
            "sherlock_records": sherlock["record_count"],
        },
        "invariants": invariants,
        "exceptions": {
            "core_errors": core_errors,
            "trace_errors": trace_errors,
            "event_errors": event_errors,
            "high_risk_direct_allow": high_risk_direct_allow,
            "camera_media_release_not_denied": camera_media_release_not_denied,
            "no_idempotency": no_idempotency,
            "no_receipts": no_receipts,
        },
        "next_runtime_targets": [
            "replace fixture policy annotation with live Guardrail Fabric CLI output",
            "replace queue projection with sourceos-syncd orchestration enqueue output",
            "replace admission projection with AgentPlane PR #130 output after merge",
            "feed sherlock index into UI workbench event stream",
        ],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/orchestration/world-class-event-loop", help="output directory")
    parser.add_argument("--compact", action="store_true", help="write compact JSON")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)

    core_bundle = sdo.fixture_bundle()
    trace_bundle = e2wm.fixture_bundle()
    event_bundle = eventcap.fixture_bundle()

    core_errors = sdo.validate_bundle(core_bundle)
    trace_errors = e2wm.validate_bundle(trace_bundle)
    event_errors = eventcap.validate_bundle(event_bundle)

    records = event_records_from_bundle(event_bundle)
    annotated = annotate_policy(records)
    admission = admission_artifact(annotated)
    queue = sourceos_queue_snapshot(annotated, admission)
    sherlock = sherlock_index(annotated)
    report = demo_report(core_errors, trace_errors, event_errors, annotated, admission, queue, sherlock)

    outputs = {
        "core-orchestration.bundle.json": core_bundle,
        "embodied-traces.bundle.json": trace_bundle,
        "embodied-training-records.json": e2wm.training_records(trace_bundle),
        "event-capability.bundle.json": event_bundle,
        "event-capability.records.json": records,
        "event-capability.policy-annotated.records.json": annotated,
        "sourceos-queue.snapshot.json": queue,
        "agentplane-admission.artifact.json": admission,
        "sherlock-event-capability-index.json": sherlock,
        "demo-report.json": report,
    }
    for name, value in outputs.items():
        write_json(out_dir / name, value, compact=args.compact)

    print("world-class event loop demo generated")
    print("out=" + str(out_dir))
    print("status=" + report["status"])
    print("records={} admitted={} waiting={} blocked={} invalid={}".format(
        len(annotated),
        admission["summary"]["admitted"],
        admission["summary"]["waiting_for_approval"],
        admission["summary"]["blocked"],
        admission["summary"]["invalid"],
    ))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
