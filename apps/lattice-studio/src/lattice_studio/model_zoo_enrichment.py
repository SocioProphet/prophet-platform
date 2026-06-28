"""Model zoo enrichment + active-metadata pipeline wiring.

Connects LatticeModelZooFixture records through the existing enrichment and
active-metadata pipeline and produces model-zoo-specific facets, agentplane
tool binding stubs, and a policy-fabric promotion gate check.
"""

from __future__ import annotations

from typing import Any

from .active_metadata import _event_from_record
from .enrichment import enrich_record_set
from .model_zoo import demo_model_zoo_entry
from .platform_records import platform_record_set


def enrich_model_zoo_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    entry = fixture["entry"]
    records = fixture["platformRecords"]
    search_enrichment = enrich_record_set(records)

    model_zoo_facets: list[dict[str, Any]] = []
    for enrichment in search_enrichment["enrichments"]:
        enrichment.setdefault("search", {}).setdefault("facets", {}).update(
            _model_zoo_facets(entry, fixture)
        )
        model_zoo_facets.append(enrichment)
    search_enrichment = {**search_enrichment, "enrichments": model_zoo_facets}

    events: list[dict[str, Any]] = []
    for record in records["records"]:
        events.append(_event_from_record("model-zoo", record))

    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelZooEnrichmentBundle",
        "entryId": entry["id"],
        "searchEnrichment": search_enrichment,
        "agentplaneBindings": model_zoo_agentplane_tools(entry),
        "policyFabricGate": model_zoo_policy_gate(entry),
        "activeMetadataEvents": events,
    }


def model_zoo_agentplane_tools(entry: dict[str, Any]) -> list[dict[str, Any]]:
    policy_ref = entry.get("usePolicyRef", "urn:srcos:policy:model-use-community-truth-demo")
    boundary = ["no-authority-grant", "no-ledger-mutation"]
    return [
        {
            "toolId": "urn:srcos:agentplane-tool:discover-model-zoo",
            "name": "discover-model-zoo",
            "description": "Discover model zoo entries by query.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "outputSchema": {
                "type": "object",
                "properties": {"entries": {"type": "array", "items": {"type": "object"}}},
                "required": ["entries"],
            },
            "policyRef": policy_ref,
            "boundary": boundary,
        },
        {
            "toolId": "urn:srcos:agentplane-tool:promote-model-zoo-entry",
            "name": "promote-model-zoo-entry",
            "description": "Promote a model zoo entry through the governed promotion gate.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entryId": {"type": "string"},
                    "approverRef": {"type": "string"},
                },
                "required": ["entryId", "approverRef"],
            },
            "outputSchema": {
                "type": "object",
                "properties": {"promotionBundle": {"type": "object"}},
                "required": ["promotionBundle"],
            },
            "policyRef": policy_ref,
            "boundary": boundary,
        },
        {
            "toolId": "urn:srcos:agentplane-tool:evaluate-model-zoo-entry",
            "name": "evaluate-model-zoo-entry",
            "description": "Trigger an evaluation run for a model zoo entry against a named evaluation bundle.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entryId": {"type": "string"},
                    "evaluationBundleRef": {"type": "string"},
                },
                "required": ["entryId", "evaluationBundleRef"],
            },
            "outputSchema": {
                "type": "object",
                "properties": {"evaluationBundle": {"type": "object"}},
                "required": ["evaluationBundle"],
            },
            "policyRef": policy_ref,
            "boundary": boundary,
        },
    ]


def model_zoo_policy_gate(entry: dict[str, Any]) -> dict[str, Any]:
    promotion_gate = entry.get("promotionGate", {})
    state = promotion_gate.get("state", "unknown")
    blocked = state == "needs-review"
    block_reasons: list[str] = []
    if blocked:
        block_reasons.append("promotionGate.state=needs-review: entry requires explicit review before promotion")
        workflow_ref = promotion_gate.get("workflowRef")
        if workflow_ref:
            block_reasons.append(f"pending workflow: {workflow_ref}")
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "PromotionGateCheck",
        "entryId": entry["id"],
        "promotionGateState": state,
        "blocked": blocked,
        "blockReasons": block_reasons,
        "policyRef": entry.get("usePolicyRef"),
    }


def _model_zoo_facets(entry: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    runtime_profile = fixture.get("runtimeProfile", {})
    evaluation = fixture.get("evaluationBundle", {})
    promotion_gate = entry.get("promotionGate", {})
    return {
        "riskTier": _risk_tier(entry),
        "servingBackends": runtime_profile.get("servingBackends", []),
        "evaluationVerdict": _evaluation_verdict(evaluation),
        "promotionGateState": promotion_gate.get("state", "unknown"),
    }


def _risk_tier(entry: dict[str, Any]) -> str:
    state = entry.get("state", "")
    gate_state = entry.get("promotionGate", {}).get("state", "")
    if state == "candidate" and gate_state == "needs-review":
        return "review-required"
    if state in ("approved", "promoted"):
        return "approved"
    return "unclassified"


def _evaluation_verdict(evaluation: dict[str, Any]) -> str:
    status = evaluation.get("status", "")
    if status in ("passed", "approved"):
        return "passed"
    if status in ("failed", "rejected"):
        return "failed"
    if status:
        return status
    return "pending"
