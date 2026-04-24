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


class AcademyPolicyEvaluator:
    def decide(self, record: LearningSearchRecord, context: AcademyPolicyContext) -> AcademyPolicyDecision:
        raise NotImplementedError


class LocalVisibilityPolicyEvaluator(AcademyPolicyEvaluator):
    def decide(self, record: LearningSearchRecord, context: AcademyPolicyContext) -> AcademyPolicyDecision:
        visibility = record.visibility
        if visibility is None:
            return AcademyPolicyDecision(allowed=True, reason="no visibility constraints")
        if visibility.allowed_actor_ids and context.actor_id not in visibility.allowed_actor_ids:
            return AcademyPolicyDecision(allowed=False, reason="actor not allowed")
        if visibility.allowed_workspace_ids and context.workspace_id not in visibility.allowed_workspace_ids:
            return AcademyPolicyDecision(allowed=False, reason="workspace not allowed")
        if visibility.allowed_jurisdiction_ids and context.jurisdiction_id not in visibility.allowed_jurisdiction_ids:
            return AcademyPolicyDecision(allowed=False, reason="jurisdiction not allowed")
        return AcademyPolicyDecision(allowed=True, reason="local visibility policy allowed")


academy_policy_evaluator: AcademyPolicyEvaluator = LocalVisibilityPolicyEvaluator()
