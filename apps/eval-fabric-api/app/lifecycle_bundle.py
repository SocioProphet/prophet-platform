from __future__ import annotations

from typing import Any

from .lifecycle_artifacts import (
    build_gate_activation_record,
    build_graduation_record,
    build_lifecycle_artifact_graph,
    build_promotion_decision,
    build_rollback_record,
)

DEFAULT_AGENT_REF = "agent://socioprophet/example/retrieval-governed-operator"
DEFAULT_RECIPE_REF = "recipe://benchmark/ray/eval-fabric-001"
DEFAULT_CURRENT_STAGE = "L3_assist_mode"
DEFAULT_TARGET_STAGE = "L4_supervised_actuation"
DEFAULT_PROMOTION_WINDOW = "rolling_30d"
DEFAULT_REQUIRED_GATES = [
    "authorization_gate",
    "scope_gate",
    "policy_gate",
    "risk_gate",
    "evidence_gate",
    "approval_gate",
    "rollback_gate",
]
DEFAULT_LANE_SCORES = {
    "capability": 3,
    "safety_policy": 4,
    "reliability_recovery": 3,
    "observability_auditability": 4,
    "provenance_reproducibility": 4,
    "efficiency_budget": 3,
    "human_oversight_acceptability": 4,
}


def _id_slug(model_release_id: str) -> str:
    return model_release_id.replace("/", "-").replace(":", "-").replace(" ", "-")


def build_lifecycle_bundle(*, model_release_id: str, agent_ref: str = DEFAULT_AGENT_REF, recipe_ref: str = DEFAULT_RECIPE_REF) -> dict[str, Any]:
    slug = _id_slug(model_release_id)
    subject_ref = f"model://{model_release_id}"

    promotion_decision = build_promotion_decision(
        promotion_decision_id=f"promotion_decision::{slug}",
        subject_ref=subject_ref,
        source_ref=recipe_ref,
        current_stage=DEFAULT_CURRENT_STAGE,
        target_stage=DEFAULT_TARGET_STAGE,
        required_gates=DEFAULT_REQUIRED_GATES,
        evidence_refs=["event_envelope", "evidence_receipt", "benchmark_report"],
        promotion_window=DEFAULT_PROMOTION_WINDOW,
    )

    rollback_record = build_rollback_record(
        rollback_record_id=f"rollback_record::{slug}",
        subject_ref="service://eval-fabric-api/ray-serve",
        trigger_ref=promotion_decision["promotion_decision_id"],
        rollback_reason="post-promotion policy regression",
        required_gates=[
            "authorization_gate",
            "scope_gate",
            "policy_gate",
            "risk_gate",
            "rollback_gate",
        ],
        evidence_refs=["event_envelope", "evidence_receipt"],
    )

    gate_activation_record = build_gate_activation_record(
        gate_activation_record_id=f"gate_activation_record::{slug}",
        action_ref="action://eval-fabric/tool_write/logical_route",
        required_gates=DEFAULT_REQUIRED_GATES,
        activated_gates=DEFAULT_REQUIRED_GATES,
        failed_gates=[],
        policy_decision_ref=f"policy://decision/{slug}",
        approval_ref=f"approval://operator/{slug}",
        rollback_requirement="required_before_side_effect",
    )

    graduation_record = build_graduation_record(
        graduation_record_id=f"graduation_record::{slug}",
        agent_ref=agent_ref,
        current_stage=DEFAULT_CURRENT_STAGE,
        target_stage=DEFAULT_TARGET_STAGE,
        lane_scores=DEFAULT_LANE_SCORES,
        blocking_lanes=[],
        promotion_window=DEFAULT_PROMOTION_WINDOW,
        required_gates=DEFAULT_REQUIRED_GATES,
        evidence_refs=[
            "event_envelope",
            "evidence_receipt",
            "benchmark_report",
            "promotion_decision",
        ],
    )

    artifact_graph = build_lifecycle_artifact_graph(
        artifact_graph_id=f"lifecycle_artifact_graph::{slug}",
        agent_ref=agent_ref,
        edges=[
            {"from": recipe_ref, "to": promotion_decision["promotion_decision_id"], "type": "promotes"},
            {"from": promotion_decision["promotion_decision_id"], "to": gate_activation_record["gate_activation_record_id"], "type": "requires_gate_activation"},
            {"from": gate_activation_record["gate_activation_record_id"], "to": graduation_record["graduation_record_id"], "type": "supports_graduation"},
            {"from": promotion_decision["promotion_decision_id"], "to": rollback_record["rollback_record_id"], "type": "rollback_ready"},
        ],
        evidence_refs=[
            "event_envelope",
            "evidence_receipt",
            "benchmark_report",
            "promotion_decision",
            "rollback_record",
            "gate_activation_record",
            "graduation_record",
        ],
    )

    return {
        "model_release_id": model_release_id,
        "agent_ref": agent_ref,
        "recipe_ref": recipe_ref,
        "promotion_decision": promotion_decision,
        "rollback_record": rollback_record,
        "gate_activation_record": gate_activation_record,
        "graduation_record": graduation_record,
        "artifact_graph": artifact_graph,
        "source": "runtime+builders",
    }
