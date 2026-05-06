#!/usr/bin/env python3
"""Fixture and validator for Embodied Experience Trace contracts.

This extends the Sovereign Device Orchestration contract with the missing E2WM
layer: trainable and evaluable state-transition traces for object permanence,
counting, plan generation, and policy-aware planning.

Run:
  python specs/orchestration/embodied_experience_trace_fixture.py
  python specs/orchestration/embodied_experience_trace_fixture.py --json
  python specs/orchestration/embodied_experience_trace_fixture.py --records
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


TASK_FAMILIES = {
    "track_count",
    "track_permanence",
    "plan_generation",
    "policy_aware_planning",
}

VALID_STEP_TYPES = {
    "observe",
    "move_object",
    "place_object",
    "enter_room",
    "sit",
    "watch",
    "propose_action",
    "policy_decision",
}

VALID_OUTCOMES = {"allowed", "denied", "requires_approval", "redacted", "degraded"}


def fixture_bundle() -> dict[str, Any]:
    return {
        "trace_version": "e2wm.sdo.v0.1",
        "bundle_id": "bundle:fixture:e2wm-household-orchestration:2026-05-06",
        "contract_refs": [
            "SocioProphet/prophet-platform/specs/orchestration/orchestration_contract_fixture.py",
            "SocioProphet/prophet-platform/specs/orchestration/embodied_experience_trace_fixture.py",
        ],
        "data_mode": "fixture",
        "world": {
            "world_id": "world:fixture:apartment-01",
            "spaces": ["kitchen", "bedroom", "living_room"],
            "surfaces": ["desk", "sofa", "bed", "floor"],
            "objects": ["cell_phone", "lime", "apple", "book", "tv_remote"],
            "devices": ["tv", "living_room_fan", "front_door_camera", "security_system"],
            "actors": ["emily", "john", "mary", "household_orchestrator_agent"],
        },
        "traces": [
            {
                "trace_id": "trace:track-count:desk-items",
                "task_family": "track_count",
                "goal": "Answer how many relevant objects are on the desk after a sequence of actions.",
                "initial_state": {
                    "objects": {
                        "cell_phone": {"location": "emily", "relation": "held_by"},
                        "lime": {"location": "emily", "relation": "held_by"},
                        "apple": {"location": "emily", "relation": "held_by"},
                    }
                },
                "steps": [
                    step("step:tc:1", "place_object", "emily", "cell_phone", "desk", before="held_by:emily", after="on:desk"),
                    step("step:tc:2", "place_object", "emily", "lime", "desk", before="held_by:emily", after="on:desk", note="Relevant because next to a phone on the same desk still counts as on the desk."),
                    step("step:tc:3", "observe", "emily", "irrelevant_action", "floor", before="none", after="none", note="Distractor action; should not change desk count."),
                    step("step:tc:4", "place_object", "emily", "apple", "desk", before="held_by:emily", after="on:desk"),
                ],
                "query": "How many items are there on the desk?",
                "expected_answer": {"answer_type": "count", "value": 3, "supporting_objects": ["cell_phone", "lime", "apple"]},
                "state_assertions": [
                    {"object_id": "cell_phone", "expected_relation": "on", "expected_location": "desk"},
                    {"object_id": "lime", "expected_relation": "on", "expected_location": "desk"},
                    {"object_id": "apple", "expected_relation": "on", "expected_location": "desk"},
                ],
                "receipt_refs": ["receipt:event:living-room-temp-high"],
            },
            {
                "trace_id": "trace:track-permanence:book-sofa",
                "task_family": "track_permanence",
                "goal": "Answer the last known location of an object after moves and distractors.",
                "initial_state": {"objects": {"book": {"location": "desk", "relation": "on"}}},
                "steps": [
                    step("step:tp:1", "observe", "john", "book", "desk", before="on:desk", after="on:desk"),
                    step("step:tp:2", "move_object", "mary", "book", "mary", before="on:desk", after="held_by:mary"),
                    step("step:tp:3", "observe", "mary", "irrelevant_action", "bedroom", before="none", after="none"),
                    step("step:tp:4", "place_object", "mary", "book", "sofa", before="held_by:mary", after="on:sofa"),
                ],
                "query": "Where was the book?",
                "expected_answer": {"answer_type": "location", "object_id": "book", "value": "sofa", "confidence": 1.0},
                "state_assertions": [{"object_id": "book", "expected_relation": "on", "expected_location": "sofa"}],
                "receipt_refs": ["receipt:event:package-delivered"],
            },
            {
                "trace_id": "trace:plan-generation:watch-tv",
                "task_family": "plan_generation",
                "goal": "Generate a physically coherent plan for watching TV.",
                "initial_state": {"actor_location": {"household_orchestrator_agent": "bedroom"}, "devices": {"tv": "off"}},
                "steps": [
                    step("step:pg:1", "enter_room", "household_orchestrator_agent", "self", "living_room", before="in:bedroom", after="in:living_room"),
                    step("step:pg:2", "sit", "household_orchestrator_agent", "self", "sofa", before="standing:living_room", after="sitting:sofa"),
                    step("step:pg:3", "watch", "household_orchestrator_agent", "tv", "living_room", before="tv:off", after="tv:watched"),
                ],
                "query": "How to watch TV?",
                "expected_answer": {
                    "answer_type": "plan",
                    "ordered_actions": ["enter_room:living_room", "sit:sofa", "watch:tv"],
                    "invalid_actions": ["stand_up_after_sitting_without_need", "walk_to_same_room_twice"],
                },
                "state_assertions": [{"object_id": "tv", "expected_relation": "watched", "expected_location": "living_room"}],
                "receipt_refs": [],
            },
            {
                "trace_id": "trace:policy-aware-planning:security-and-camera",
                "task_family": "policy_aware_planning",
                "goal": "Generate a plan that distinguishes allowed observation from high-risk actuation and raw camera export.",
                "initial_state": {
                    "devices": {
                        "front_door_camera": "online",
                        "security_system": "disarmed",
                    }
                },
                "steps": [
                    step("step:pa:1", "propose_action", "household_orchestrator_agent", "security_system", "home", before="disarmed", after="proposal:arm_alarm", policy_outcome="requires_approval"),
                    step("step:pa:2", "policy_decision", "guardrail_fabric", "security_system", "home", before="proposal:arm_alarm", after="requires_approval", policy_outcome="requires_approval"),
                    step("step:pa:3", "propose_action", "household_orchestrator_agent", "front_door_camera", "home", before="metadata_only", after="proposal:export_raw_video", policy_outcome="denied"),
                    step("step:pa:4", "policy_decision", "guardrail_fabric", "front_door_camera", "home", before="proposal:export_raw_video", after="denied", policy_outcome="denied"),
                ],
                "query": "Can the agent arm security and export raw camera video without approval?",
                "expected_answer": {
                    "answer_type": "policy_grounded_answer",
                    "value": "security arming requires approval; raw camera export is denied by default",
                    "policy_outcomes": ["requires_approval", "denied"],
                },
                "state_assertions": [
                    {"object_id": "security_system", "expected_relation": "requires_approval", "expected_location": "home"},
                    {"object_id": "front_door_camera", "expected_relation": "denied", "expected_location": "home"},
                ],
                "receipt_refs": ["receipt:policy:requires-approval-arm-security", "receipt:policy:deny-raw-camera-export"],
            },
        ],
    }


def step(
    step_id: str,
    step_type: str,
    actor_id: str,
    object_id: str,
    location_id: str,
    *,
    before: str,
    after: str,
    note: str | None = None,
    policy_outcome: str | None = None,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "step_id": step_id,
        "step_type": step_type,
        "actor_id": actor_id,
        "object_id": object_id,
        "location_id": location_id,
        "state_before": before,
        "state_after": after,
    }
    if note:
        obj["note"] = note
    if policy_outcome:
        obj["policy_outcome"] = policy_outcome
    return obj


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bundle.get("trace_version") != "e2wm.sdo.v0.1":
        errors.append("trace_version must be e2wm.sdo.v0.1")
    if bundle.get("data_mode") != "fixture":
        errors.append("data_mode must be fixture for bootstrap traces")

    world = bundle.get("world") or {}
    known_entities = set(world.get("objects", [])) | set(world.get("devices", [])) | {"self", "irrelevant_action"}
    known_locations = set(world.get("spaces", [])) | set(world.get("surfaces", [])) | set(world.get("actors", [])) | {"home"}
    known_actors = set(world.get("actors", [])) | {"guardrail_fabric"}

    trace_ids: set[str] = set()
    for trace in bundle.get("traces", []):
        trace_id = trace.get("trace_id")
        if not trace_id:
            errors.append("trace missing trace_id")
            continue
        if trace_id in trace_ids:
            errors.append("duplicate trace_id: " + trace_id)
        trace_ids.add(trace_id)

        if trace.get("task_family") not in TASK_FAMILIES:
            errors.append(trace_id + ": invalid task_family")
        if not trace.get("query"):
            errors.append(trace_id + ": missing query")
        if not trace.get("expected_answer"):
            errors.append(trace_id + ": missing expected_answer")

        step_ids: set[str] = set()
        for trace_step in trace.get("steps", []):
            step_id = trace_step.get("step_id")
            if not step_id:
                errors.append(trace_id + ": step missing step_id")
                continue
            if step_id in step_ids:
                errors.append(trace_id + ": duplicate step_id " + step_id)
            step_ids.add(step_id)
            if trace_step.get("step_type") not in VALID_STEP_TYPES:
                errors.append(trace_id + ": invalid step_type " + str(trace_step.get("step_type")))
            if trace_step.get("actor_id") not in known_actors:
                errors.append(trace_id + ": unknown actor " + str(trace_step.get("actor_id")))
            if trace_step.get("object_id") not in known_entities:
                errors.append(trace_id + ": unknown object/device " + str(trace_step.get("object_id")))
            if trace_step.get("location_id") not in known_locations:
                errors.append(trace_id + ": unknown location " + str(trace_step.get("location_id")))
            if not trace_step.get("state_before") or not trace_step.get("state_after"):
                errors.append(trace_id + ": step missing state transition")
            if trace_step.get("policy_outcome") and trace_step["policy_outcome"] not in VALID_OUTCOMES:
                errors.append(trace_id + ": invalid policy_outcome")

        if trace.get("task_family") == "track_count":
            expected = trace.get("expected_answer", {})
            if expected.get("answer_type") != "count" or not isinstance(expected.get("value"), int):
                errors.append(trace_id + ": track_count expected answer must be integer count")
            if len(expected.get("supporting_objects", [])) != expected.get("value"):
                errors.append(trace_id + ": supporting object count does not match expected count")

        if trace.get("task_family") == "plan_generation":
            actions = trace.get("expected_answer", {}).get("ordered_actions", [])
            if not actions or actions[-1] != "watch:tv":
                errors.append(trace_id + ": plan_generation must end with watch:tv")

        if trace.get("task_family") == "policy_aware_planning":
            outcomes = set(trace.get("expected_answer", {}).get("policy_outcomes", []))
            if not {"requires_approval", "denied"}.issubset(outcomes):
                errors.append(trace_id + ": policy-aware trace must include approval and denial")

    required_families = {trace.get("task_family") for trace in bundle.get("traces", [])}
    for family in TASK_FAMILIES:
        if family not in required_families:
            errors.append("missing task family: " + family)

    return errors


def training_records(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for trace in bundle["traces"]:
        records.append(
            {
                "record_id": "record:" + trace["trace_id"].split(":", 1)[1],
                "task_family": trace["task_family"],
                "input": {
                    "goal": trace["goal"],
                    "steps": trace["steps"],
                    "query": trace["query"],
                },
                "target": trace["expected_answer"],
                "state_assertions": trace.get("state_assertions", []),
                "receipt_refs": trace.get("receipt_refs", []),
            }
        )
    return records


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit full trace bundle")
    parser.add_argument("--records", action="store_true", help="emit train/eval records")
    args = parser.parse_args(argv)

    bundle = fixture_bundle()
    errors = validate_bundle(bundle)

    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0 if not errors else 1
    if args.records:
        print(json.dumps(training_records(bundle), indent=2, sort_keys=True))
        return 0 if not errors else 1

    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1

    print("embodied experience trace validation passed")
    print("traces={} training_records={}".format(len(bundle["traces"]), len(training_records(bundle))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
