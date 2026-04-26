"""Deterministic enrichment for Lattice platform asset records.

The enrichment layer is intentionally rule-based for this tranche. It gives
Sherlock Search, Slash Topics, New Hope, ContractForge, Policy Fabric, and later
metadata/language-modeling workflows a shared sidecar without forking the
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

    topics = topic_candidates(asset_kind=asset_kind, producer_repo=producer_repo, promotion_channel=promotion_channel)
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordEnrichment",
        "assetId": asset_id,
        "search": {
            "docType": "lattice.platformAssetRecord",
            "title": f"{record.get('name')} {record.get('version')}",
            "facets": {
                "assetKind": asset_kind,
                "producerRepo": producer_repo,
                "promotionChannel": promotion_channel,
                "compatibilitySurfaces": [str(surface) for surface in compatibility_surfaces],
            },
        },
        "slashTopics": topics,
        "newHope": {
            "carrierKind": "PlatformAssetRecordCarrier",
            "entityId": asset_id,
            "citationSource": producer_repo,
            "lensCandidates": [str(surface) for surface in compatibility_surfaces],
            "membraneStatus": "candidate",
        },
        "contractForge": {
            "subjectClass": contract_subject_class(asset_kind),
            "lifecycleStatus": lifecycle_status(promotion_channel),
            "evidenceRef": record.get("evidenceCorrelationId"),
        },
        "policyFabric": {
            "subjectClass": policy_subject_class(asset_kind),
            "gateStatus": policy_gate_status(promotion_channel),
            "policyRef": record.get("policyRef"),
        },
        "languageModeling": {
            "use": "metadata-classification-and-governance-explanation",
            "plainLanguageSummary": summary_for(record),
            "controlledVocabularyTerms": sorted(set(term.strip("/").replace("/", ".") for term in topics)),
            "classificationLabels": classifier_labels(asset_kind=asset_kind, producer_repo=producer_repo, promotion_channel=promotion_channel),
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


def topic_candidates(*, asset_kind: str, producer_repo: str, promotion_channel: object) -> list[str]:
    topics = {"/lattice", "/governance", "/evidence", "/provenance"}
    if asset_kind == "boot-release-set":
        topics.update({"/lattice/boot", "/sourceos", "/sourceos/boot", "/sourceos/recovery", "/release"})
    if asset_kind == "runtime-asset":
        topics.update({"/lattice/runtime", "/lattice/forge", "/notebook", "/agentplane", "/supply-chain"})
    if producer_repo == "SourceOS-Linux/sourceos-boot":
        topics.update({"/sourceos", "/boot", "/recovery"})
    if producer_repo == "SocioProphet/lattice-forge":
        topics.update({"/forge", "/runtime", "/supply-chain"})
    if isinstance(promotion_channel, str) and promotion_channel:
        topics.add(f"/lifecycle/{promotion_channel}")
    topics.update({"/contracts", "/policy", "/modeling"})
    return sorted(topics)


def contract_subject_class(asset_kind: str) -> str:
    return {
        "boot-release-set": "BootReleaseContractReferencedAsset",
        "runtime-asset": "RuntimeContractReferencedAsset",
    }.get(asset_kind, "GenericContractReferencedAsset")


def policy_subject_class(asset_kind: str) -> str:
    return {
        "boot-release-set": "BootReleasePolicySubject",
        "runtime-asset": "RuntimePolicySubject",
    }.get(asset_kind, "GenericPolicySubject")


def lifecycle_status(promotion_channel: object) -> str:
    if promotion_channel in {"stable", "emergency"}:
        return "approved"
    if promotion_channel == "deprecated":
        return "deprecated"
    return "candidate"


def policy_gate_status(promotion_channel: object) -> str:
    if promotion_channel == "stable":
        return "eligible-for-standard-use"
    if promotion_channel == "emergency":
        return "eligible-for-emergency-use"
    if promotion_channel == "deprecated":
        return "blocked-deprecated"
    return "candidate-review-required"


def classifier_labels(*, asset_kind: str, producer_repo: str, promotion_channel: object) -> list[str]:
    labels = [asset_kind, producer_repo.replace("/", ":")]
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
