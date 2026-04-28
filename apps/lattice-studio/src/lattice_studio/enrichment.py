"""Deterministic search/topic/governance enrichments for Lattice Studio records.

Lattice Studio emits PlatformAssetRecord objects for catalog assets, notebook
sessions, workspace sources, workspace source bindings, synthesis artifacts, and
publication receipts. This module creates sidecar enrichments for Sherlock
Search, Slash Topics, and New Hope-style semantic governance without mutating the
canonical PlatformAssetRecord identity.
"""

from __future__ import annotations

from typing import Any


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    asset_id = _required_str(record, "assetId")
    asset_kind = _required_str(record, "assetKind")
    producer_repo = _required_str(record, "producerRepo")
    promotion_channel = record.get("promotionChannel")
    compatibility_surfaces = record.get("compatibilitySurfaces", [])
    if not isinstance(compatibility_surfaces, list):
        compatibility_surfaces = []
    topics = topic_candidates(
        asset_kind=asset_kind,
        producer_repo=producer_repo,
        promotion_channel=promotion_channel,
        compatibility_surfaces=[str(surface) for surface in compatibility_surfaces],
    )
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordEnrichment",
        "assetId": asset_id,
        "search": {
            "docType": "lattice.platformAssetRecord",
            "title": f"{record.get('name')} {record.get('version')}",
            "body": summary_for(record),
            "facets": {
                "assetKind": asset_kind,
                "producerRepo": producer_repo,
                "promotionChannel": promotion_channel,
                "compatibilitySurfaces": [str(surface) for surface in compatibility_surfaces],
                "sourceKind": record.get("sourceKind"),
            },
        },
        "slashTopics": topics,
        "newHope": {
            "carrierKind": "PlatformAssetRecordCarrier",
            "entityId": asset_id,
            "citationSource": producer_repo,
            "lensCandidates": [str(surface) for surface in compatibility_surfaces],
            "membraneStatus": membrane_status(asset_kind),
        },
        "governance": {
            "assetClass": asset_class(asset_kind),
            "surfaceScope": surface_scope(asset_kind, [str(surface) for surface in compatibility_surfaces]),
            "evidenceCompleteness": evidence_completeness(record),
            "searchVisibility": search_visibility(record),
            "policyRef": record.get("policyRef"),
            "evidenceCorrelationId": record.get("evidenceCorrelationId"),
        },
        "languageModeling": {
            "use": "source-grounded-workspace-and-lattice-metadata-classification",
            "plainLanguageSummary": summary_for(record),
            "controlledVocabularyTerms": sorted(set(term.strip("/").replace("/", ".") for term in topics)),
            "classificationLabels": classifier_labels(
                asset_kind=asset_kind,
                producer_repo=producer_repo,
                promotion_channel=promotion_channel,
            ),
            "negativeConstraints": ["do-not-overwrite-canonical-platform-asset-record"],
        },
    }


def enrich_record_set(record_set: dict[str, Any]) -> dict[str, Any]:
    if record_set.get("kind") != "PlatformAssetRecordSet":
        raise ValueError("record_set.kind must be PlatformAssetRecordSet")
    records = record_set.get("records")
    if not isinstance(records, list):
        raise ValueError("record_set.records must be a list")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordEnrichmentSet",
        "enrichments": [enrich_record(record) for record in records if isinstance(record, dict)],
    }


def topic_candidates(
    *,
    asset_kind: str,
    producer_repo: str,
    promotion_channel: object,
    compatibility_surfaces: list[str],
) -> list[str]:
    topics = {"/lattice", "/lattice/studio", "/governance", "/evidence", "/provenance"}
    if asset_kind.startswith("workspace-"):
        topics.update({"/workspace", "/workspace/source", "/workspace/evidence", "/notebooklm-class"})
    if asset_kind == "workspace-docs":
        topics.update({"/workspace/docs", "/office/docs", "/source-grounding"})
    if asset_kind == "workspace-sheets":
        topics.update({"/workspace/sheets", "/office/sheets", "/data", "/analytics"})
    if asset_kind == "workspace-slides":
        topics.update({"/workspace/slides", "/office/slides", "/publication"})
    if asset_kind == "workspace-source-binding":
        topics.update({"/workspace/binding", "/notebook/session", "/runtime/binding"})
    if asset_kind == "workspace-synthesis-artifact":
        topics.update({"/workspace/synthesis", "/source-grounded-synthesis", "/publication/draft"})
    if asset_kind.startswith("workspace-action-"):
        topics.update({"/workspace/action", "/workspace/publication", "/receipt"})
    if asset_kind == "notebook-session":
        topics.update({"/notebook", "/notebook/session", "/runtime/binding"})
    if asset_kind.startswith("catalog-"):
        topics.update({"/catalog", "/datahub", "/lattice/catalog"})
    if "prophet-workspace" in compatibility_surfaces:
        topics.add("/prophet-workspace")
    if "sherlock-search" in compatibility_surfaces:
        topics.add("/sherlock-search")
    if "slash-topics" in compatibility_surfaces:
        topics.add("/slash-topics")
    if producer_repo == "SocioProphet/prophet-workspace":
        topics.update({"/prophet-workspace", "/office"})
    if producer_repo == "SocioProphet/prophet-platform":
        topics.update({"/prophet-platform", "/platform"})
    if isinstance(promotion_channel, str) and promotion_channel:
        topics.add(f"/lifecycle/{promotion_channel}")
    return sorted(topics)


def asset_class(asset_kind: str) -> str:
    if asset_kind.startswith("workspace-action-"):
        return "workspace-action-receipt"
    if asset_kind.startswith("workspace-"):
        return "workspace-source-grounding"
    if asset_kind == "notebook-session":
        return "notebook-session"
    if asset_kind.startswith("catalog-"):
        return "catalog-asset"
    return "lattice-asset"


def surface_scope(asset_kind: str, compatibility_surfaces: list[str]) -> str:
    if asset_kind.startswith("workspace-") or "prophet-workspace" in compatibility_surfaces:
        return "workspace-lattice-studio"
    if asset_kind == "notebook-session":
        return "notebook-runtime"
    return "lattice-platform"


def membrane_status(asset_kind: str) -> str:
    if asset_kind.startswith("workspace-"):
        return "source-grounding-candidate"
    return "candidate"


def evidence_completeness(record: dict[str, Any]) -> str:
    if record.get("evidenceCorrelationId") and record.get("policyRef"):
        return "policy-and-evidence-linked"
    if record.get("evidenceCorrelationId"):
        return "evidence-linked"
    return "needs-evidence"


def search_visibility(record: dict[str, Any]) -> str:
    if record.get("policyRef"):
        return "policy-scoped"
    return "candidate-review-required"


def classifier_labels(*, asset_kind: str, producer_repo: str, promotion_channel: object) -> list[str]:
    labels = [asset_kind, producer_repo.replace("/", ":")]
    if asset_kind.startswith("workspace-"):
        labels.append("workspace-grounding")
    if isinstance(promotion_channel, str) and promotion_channel:
        labels.append(f"channel:{promotion_channel}")
    return labels


def summary_for(record: dict[str, Any]) -> str:
    name = record.get("name")
    version = record.get("version")
    asset_kind = record.get("assetKind")
    producer_repo = record.get("producerRepo")
    return f"{asset_kind} {name} version {version} produced by {producer_repo}."


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
