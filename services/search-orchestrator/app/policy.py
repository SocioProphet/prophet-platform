from __future__ import annotations

from dataclasses import dataclass

from app.models import LearningSearchRecord


@dataclass(frozen=True)
class AcademyPolicyContext:
    actor_id: str
    workspace_id: str | None = None
    jurisdiction_id: str | None = None


@dataclass(frozen=True)
class AcademyPolicyDecision:
    allowed: bool
    reason: str
    decision_ref: str = "policy-fabric://local-fallback/academy-search-visibility"
    request: dict[str, object] | None = None
    decision: dict[str, object] | None = None


class AcademyPolicyEvaluator:
    def decide(self, record: LearningSearchRecord, context: AcademyPolicyContext) -> AcademyPolicyDecision:
        raise NotImplementedError


def build_academy_visibility_request(record: LearningSearchRecord, context: AcademyPolicyContext) -> dict[str, object]:
    visibility = record.visibility
    return {
        "request_id": f"academy_visibility_request::{record.header.object_id}",
        "action": "academy.search.read",
        "actor": {
            "actor_id": context.actor_id,
            "workspace_id": context.workspace_id,
            "jurisdiction_id": context.jurisdiction_id,
        },
        "resource": {
            "resource_id": record.header.object_id,
            "source": record.source,
            "entity_type": record.entity_type,
            "target_ref": record.target_ref,
            "policy_tags": record.header.policy_tags,
            "visibility": visibility.model_dump(mode="json") if visibility else {},
        },
        "evidence_refs": record.evidence_ref_ids,
        "governance_refs": record.governance_ref_ids,
    }


def build_academy_visibility_decision(
    *,
    request: dict[str, object],
    allowed: bool,
    reason: str,
    context: AcademyPolicyContext,
    record: LearningSearchRecord,
) -> dict[str, object]:
    return {
        "policy_decision_id": f"academy_visibility_decision::{record.header.object_id}",
        "request_id": str(request["request_id"]),
        "subject_ref": f"academy://search-record/{record.header.object_id}",
        "action_ref": "action://academy/search/read",
        "decision": "allow" if allowed else "deny",
        "required_gates": [
            "actor_gate",
            "workspace_gate",
            "jurisdiction_gate",
            "policy_tag_gate",
            "evidence_gate",
        ],
        "reason": reason,
        "visibility_scope": {
            "actor_id": context.actor_id,
            "workspace_id": context.workspace_id,
            "jurisdiction_id": context.jurisdiction_id,
        },
        "validation_evidence": [str(request["request_id"])],
        "notes": ["Local fallback decision shaped to Policy Fabric Academy visibility contract."],
    }


class LocalVisibilityPolicyEvaluator(AcademyPolicyEvaluator):
    def decide(self, record: LearningSearchRecord, context: AcademyPolicyContext) -> AcademyPolicyDecision:
        request = build_academy_visibility_request(record, context)
        visibility = record.visibility
        allowed = True
        reason = "no visibility constraints"
        if visibility is not None:
            if visibility.allowed_actor_ids and context.actor_id not in visibility.allowed_actor_ids:
                allowed = False
                reason = "actor not allowed"
            elif visibility.allowed_workspace_ids and context.workspace_id not in visibility.allowed_workspace_ids:
                allowed = False
                reason = "workspace not allowed"
            elif visibility.allowed_jurisdiction_ids and context.jurisdiction_id not in visibility.allowed_jurisdiction_ids:
                allowed = False
                reason = "jurisdiction not allowed"
            else:
                reason = "local visibility policy allowed"
        decision = build_academy_visibility_decision(
            request=request,
            allowed=allowed,
            reason=reason,
            context=context,
            record=record,
        )
        return AcademyPolicyDecision(
            allowed=allowed,
            reason=reason,
            decision_ref=f"policy-fabric://decision/{decision['policy_decision_id']}",
            request=request,
            decision=decision,
        )


academy_policy_evaluator: AcademyPolicyEvaluator = LocalVisibilityPolicyEvaluator()
