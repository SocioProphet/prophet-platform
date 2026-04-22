from __future__ import annotations

from typing import Any


def build_promotion_decision(
    *,
    promotion_decision_id: str,
    subject_ref: str,
    source_ref: str,
    current_stage: str,
    target_stage: str,
    required_gates: list[str],
    evidence_refs: list[str],
    promotion_window: str,
    decision: str = "approved_with_gates",
) -> dict[str, Any]:
    return {
        "promotion_decision_id": promotion_decision_id,
        "subject_ref": subject_ref,
        "source_ref": source_ref,
        "current_stage": current_stage,
        "target_stage": target_stage,
        "decision": decision,
        "required_gates": required_gates,
        "evidence_refs": evidence_refs,
        "promotion_window": promotion_window,
    }


def build_rollback_record(
    *,
    rollback_record_id: str,
    subject_ref: str,
    trigger_ref: str,
    rollback_reason: str,
    required_gates: list[str],
    evidence_refs: list[str],
    status: str = "rollback_ready",
) -> dict[str, Any]:
    return {
        "rollback_record_id": rollback_record_id,
        "subject_ref": subject_ref,
        "trigger_ref": trigger_ref,
        "rollback_reason": rollback_reason,
        "required_gates": required_gates,
        "evidence_refs": evidence_refs,
        "status": status,
    }


def build_gate_activation_record(
    *,
    gate_activation_record_id: str,
    action_ref: str,
    required_gates: list[str],
    activated_gates: list[str],
    failed_gates: list[str],
    policy_decision_ref: str,
    approval_ref: str,
    rollback_requirement: str,
) -> dict[str, Any]:
    return {
        "gate_activation_record_id": gate_activation_record_id,
        "action_ref": action_ref,
        "required_gates": required_gates,
        "activated_gates": activated_gates,
        "failed_gates": failed_gates,
        "policy_decision_ref": policy_decision_ref,
        "approval_ref": approval_ref,
        "rollback_requirement": rollback_requirement,
    }


def build_graduation_record(
    *,
    graduation_record_id: str,
    agent_ref: str,
    current_stage: str,
    target_stage: str,
    lane_scores: dict[str, int],
    blocking_lanes: list[str],
    promotion_window: str,
    required_gates: list[str],
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "graduation_record_id": graduation_record_id,
        "agent_ref": agent_ref,
        "current_stage": current_stage,
        "target_stage": target_stage,
        "lane_scores": lane_scores,
        "blocking_lanes": blocking_lanes,
        "promotion_window": promotion_window,
        "required_gates": required_gates,
        "evidence_refs": evidence_refs,
    }


def build_lifecycle_artifact_graph(
    *,
    artifact_graph_id: str,
    agent_ref: str,
    edges: list[dict[str, str]],
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "artifact_graph_id": artifact_graph_id,
        "agent_ref": agent_ref,
        "edges": edges,
        "evidence_refs": evidence_refs,
    }
