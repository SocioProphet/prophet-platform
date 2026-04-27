"""Lampstand local search bridge for Lattice Studio DataHub.

Lampstand local search is the local-first discovery/action layer. It turns local
workspace findings into governed candidates, context packs, memory events, and
DataHub promotion proposals without directly mutating the catalog.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

DetectedAssetType = Literal[
    "data",
    "ml-model",
    "application",
    "service",
    "notebook",
    "workflow",
    "memory",
    "unknown",
]
SuggestedAction = Literal[
    "open-notebook",
    "open-terminal",
    "open-browser",
    "attach-coding-agent",
    "create-catalog-asset",
    "link-catalog-version",
    "create-notebook-session",
    "create-paas-plan",
    "emit-memory",
    "request-policy-review",
]


@dataclass(frozen=True)
class LampstandLocalSearchResult:
    result_id: str
    source: str
    local_uri: str
    title: str
    summary: str
    detected_asset_type: DetectedAssetType
    candidate_catalog_asset_id: str | None
    linked_platform_asset_id: str | None
    memory_event_refs: list[str]
    suggested_actions: list[SuggestedAction]
    evidence_refs: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "LampstandLocalSearchResult",
            "resultId": self.result_id,
            "source": self.source,
            "localUri": self.local_uri,
            "title": self.title,
            "summary": self.summary,
            "detectedAssetType": self.detected_asset_type,
            "candidateCatalogAssetId": self.candidate_catalog_asset_id,
            "linkedPlatformAssetId": self.linked_platform_asset_id,
            "memoryEventRefs": self.memory_event_refs,
            "suggestedActions": self.suggested_actions,
            "evidenceRefs": self.evidence_refs,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class LampstandContextPack:
    context_pack_id: str
    result_ids: list[str]
    workspace_ref: str
    summary: str
    recommended_actions: list[SuggestedAction]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "LampstandContextPack",
            "contextPackId": self.context_pack_id,
            "resultIds": self.result_ids,
            "workspaceRef": self.workspace_ref,
            "summary": self.summary,
            "recommendedActions": self.recommended_actions,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class DataHubPromotionProposal:
    proposal_id: str
    local_result_id: str
    proposed_catalog_asset_id: str
    proposed_asset_type: DetectedAssetType
    proposed_version: str
    required_policy_review: bool
    evidence_refs: list[str]
    suggested_topics: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "DataHubPromotionProposal",
            "proposalId": self.proposal_id,
            "localResultId": self.local_result_id,
            "proposedCatalogAssetId": self.proposed_catalog_asset_id,
            "proposedAssetType": self.proposed_asset_type,
            "proposedVersion": self.proposed_version,
            "requiredPolicyReview": self.required_policy_review,
            "evidenceRefs": self.evidence_refs,
            "suggestedTopics": self.suggested_topics,
            "createdAt": self.created_at,
        }


def demo_local_search_results() -> list[LampstandLocalSearchResult]:
    return [
        _result(
            source="sourceos-local-files",
            local_uri="file://$WORKSPACE/data/demo-csv/data.csv",
            title="Demo CSV Dataset",
            summary="Local CSV file candidate for governed DataHub promotion.",
            detected_asset_type="data",
            candidate_catalog_asset_id="catalog://datasets/demo-csv",
            linked_platform_asset_id="catalog-asset:catalog://datasets/demo-csv@0.1.0",
            suggested_actions=["open-notebook", "create-catalog-asset", "emit-memory", "request-policy-review"],
        ),
        _result(
            source="sourceos-local-files",
            local_uri="file://$WORKSPACE/models/demo-classifier/model.onnx",
            title="Demo Classifier Model",
            summary="Local model artifact candidate linked to the demo dataset and runtime.",
            detected_asset_type="ml-model",
            candidate_catalog_asset_id="catalog://models/demo-classifier",
            linked_platform_asset_id="catalog-asset:catalog://models/demo-classifier@0.1.0",
            suggested_actions=["create-notebook-session", "link-catalog-version", "emit-memory", "request-policy-review"],
        ),
        _result(
            source="browser-surface",
            local_uri="http://localhost:3000/demo",
            title="Demo Notebook Application",
            summary="Local browser surface for a notebook-backed application.",
            detected_asset_type="application",
            candidate_catalog_asset_id="catalog://applications/demo-notebook-app",
            linked_platform_asset_id="catalog-asset:catalog://applications/demo-notebook-app@0.1.0",
            suggested_actions=["open-browser", "create-paas-plan", "emit-memory"],
        ),
        _result(
            source="terminal-history",
            local_uri="local://terminal/default#pytest-services-demo",
            title="Demo Inference Service Smoke Test",
            summary="Terminal-discovered service smoke test that can become deployment evidence.",
            detected_asset_type="service",
            candidate_catalog_asset_id="catalog://services/demo-inference-service",
            linked_platform_asset_id="catalog-asset:catalog://services/demo-inference-service@0.1.0",
            suggested_actions=["open-terminal", "create-paas-plan", "attach-coding-agent", "emit-memory"],
        ),
    ]


def _result(
    *,
    source: str,
    local_uri: str,
    title: str,
    summary: str,
    detected_asset_type: DetectedAssetType,
    candidate_catalog_asset_id: str,
    linked_platform_asset_id: str,
    suggested_actions: list[SuggestedAction],
) -> LampstandLocalSearchResult:
    seed = json.dumps(
        {"source": source, "localUri": local_uri, "title": title, "detectedAssetType": detected_asset_type},
        sort_keys=True,
        separators=(",", ":"),
    )
    result_id = "lampstand-result:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return LampstandLocalSearchResult(
        result_id=result_id,
        source=source,
        local_uri=local_uri,
        title=title,
        summary=summary,
        detected_asset_type=detected_asset_type,
        candidate_catalog_asset_id=candidate_catalog_asset_id,
        linked_platform_asset_id=linked_platform_asset_id,
        memory_event_refs=[f"memory://{result_id}"],
        suggested_actions=suggested_actions,
        evidence_refs=[f"evidence://{result_id}"],
    )


def context_pack_for_results(results: list[LampstandLocalSearchResult], *, workspace_ref: str) -> LampstandContextPack:
    result_ids = sorted(result.result_id for result in results)
    actions = sorted({action for result in results for action in result.suggested_actions})
    seed = json.dumps({"workspaceRef": workspace_ref, "resultIds": result_ids}, sort_keys=True, separators=(",", ":"))
    return LampstandContextPack(
        context_pack_id="lampstand-context-pack:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        result_ids=result_ids,
        workspace_ref=workspace_ref,
        summary="Local context pack for DataHub promotion, notebook work, PaaS deployment, memory, and agent actions.",
        recommended_actions=actions,
    )


def promotion_proposals_for_results(results: list[LampstandLocalSearchResult]) -> list[DataHubPromotionProposal]:
    proposals = []
    for result in results:
        if result.candidate_catalog_asset_id is None:
            continue
        seed = json.dumps({"resultId": result.result_id, "catalogAssetId": result.candidate_catalog_asset_id}, sort_keys=True, separators=(",", ":"))
        proposals.append(
            DataHubPromotionProposal(
                proposal_id="datahub-promotion:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
                local_result_id=result.result_id,
                proposed_catalog_asset_id=result.candidate_catalog_asset_id,
                proposed_asset_type=result.detected_asset_type,
                proposed_version="0.1.0",
                required_policy_review=True,
                evidence_refs=result.evidence_refs,
                suggested_topics=topics_for_asset_type(result.detected_asset_type),
            )
        )
    return proposals


def topics_for_asset_type(asset_type: DetectedAssetType) -> list[str]:
    base = ["/lattice", "/datahub", "/lampstand", "/local-search", "/evidence", "/policy"]
    specific = {
        "data": ["/data", "/catalog/data"],
        "ml-model": ["/ml", "/catalog/model"],
        "application": ["/applications", "/catalog/application"],
        "service": ["/services", "/catalog/service", "/paas"],
        "notebook": ["/notebooks", "/lattice-studio"],
        "workflow": ["/workflows", "/automation"],
        "memory": ["/memory"],
        "unknown": ["/unclassified"],
    }[asset_type]
    return sorted(set(base + specific))


def local_search_result_to_platform_record(result: LampstandLocalSearchResult) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": result.result_id,
        "assetKind": f"lampstand-local-{result.detected_asset_type}",
        "name": result.title,
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "LampstandLocalSearchResult",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": None,
        "evidenceCorrelationId": result.result_id,
        "promotionChannel": "local-candidate",
        "compatibilitySurfaces": [
            "lampstand-local-search",
            "lattice-studio",
            "sourceos-local",
            "memory-mesh",
            "sherlock-search",
            "slash-topics",
        ],
    }
