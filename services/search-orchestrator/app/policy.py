from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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
        "required_gates": ["actor_gate", "workspace_gate", "jurisdiction_gate", "policy_tag_gate", "evidence_gate"],
        "reason": reason,
        "visibility_scope": {
            "actor_id": context.actor_id,
            "workspace_id": context.workspace_id,
            "jurisdiction_id": context.jurisdiction_id,
        },
        "validation_evidence": [str(request["request_id"])],
        "notes": ["Local fallback decision shaped to Policy Fabric Academy visibility contract."],
    }


def policy_decision_from_payload(payload: dict[str, object], request: dict[str, object]) -> AcademyPolicyDecision:
    decision_value = payload.get("decision")
    allowed = decision_value == "allow"
    reason = str(payload.get("reason", "policy fabric decision"))
    decision_id = str(payload.get("policy_decision_id", "unknown"))
    return AcademyPolicyDecision(
        allowed=allowed,
        reason=reason,
        decision_ref=f"policy-fabric://decision/{decision_id}",
        request=request,
        decision=payload,
    )


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
        return policy_decision_from_payload(decision, request)


class HttpPolicyFabricEvaluator(AcademyPolicyEvaluator):
    def __init__(self, endpoint: str, fallback: AcademyPolicyEvaluator | None = None, timeout_seconds: float = 2.0) -> None:
        self.endpoint = endpoint
        self.fallback = fallback or LocalVisibilityPolicyEvaluator()
        self.timeout_seconds = timeout_seconds

    def decide(self, record: LearningSearchRecord, context: AcademyPolicyContext) -> AcademyPolicyDecision:
        request_payload = build_academy_visibility_request(record, context)
        body = json.dumps(request_payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Policy Fabric response must be a JSON object")
            return policy_decision_from_payload(payload, request_payload)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
            return self.fallback.decide(record, context)


def build_academy_policy_evaluator() -> AcademyPolicyEvaluator:
    endpoint = os.environ.get("SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT")
    if endpoint:
        timeout = float(os.environ.get("SEARCH_ORCHESTRATOR_POLICY_FABRIC_TIMEOUT_SECONDS", "2.0"))
        return HttpPolicyFabricEvaluator(endpoint=endpoint, timeout_seconds=timeout)
    return LocalVisibilityPolicyEvaluator()


academy_policy_evaluator: AcademyPolicyEvaluator = build_academy_policy_evaluator()
