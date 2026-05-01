"""Lattice Studio/Data/GovernAI product spine fixture.

This module emits one deterministic vertical-slice fixture for the approved
Lattice Studio/Data/GovernAI lane:

CatalogAsset -> DataProduct -> AnnotationSet -> RuntimeAsset -> NotebookSession
-> QueryRun -> PromotionCandidate -> EvaluationBundle -> Factsheet
-> PublicationArtifact -> PlatformAssetRecord.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .catalog import demo_catalog_asset
from .platform_records import platform_record_set
from .session import create_session


def _digest(payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _record(asset_id: str, asset_kind: str, name: str, source_kind: str, policy_ref: str | None, evidence_id: str | None, surfaces: list[str]) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": asset_id,
        "assetKind": asset_kind,
        "name": name,
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": source_kind,
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": policy_ref,
        "evidenceCorrelationId": evidence_id,
        "promotionChannel": "lattice-data-governai-demo",
        "compatibilitySurfaces": surfaces,
    }


def demo_runtime_asset() -> dict[str, Any]:
    return {
        "apiVersion": "forge.socioprophet.dev/v1",
        "kind": "RuntimeAsset",
        "runtimeAssetId": "runtime-asset:prophet-python-ml:0.1.0",
        "name": "prophet-python-ml",
        "version": "0.1.0",
        "kernel": {"name": "prophet-python-ml-0.1.0"},
        "policyRef": "policy://runtime/prophet-python-ml-demo",
        "evidenceRef": "urn:srcos:evidence:runtime-prophet-python-ml-demo",
    }


def demo_data_product(catalog_asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "DataProduct",
        "id": "urn:srcos:data-product:community_truth_demo",
        "name": "Community Truth Demo Data Product",
        "catalogAssetRef": catalog_asset["catalogAssetId"],
        "contractRef": "urn:srcos:data-contract:community_truth_demo",
        "qualityProfileRef": "urn:srcos:quality-profile:community_truth_demo",
        "policyRef": "urn:srcos:policy:lattice-data-product-demo",
        "licensePolicyRef": "urn:srcos:license-policy:demo-open-review",
        "trust": {"datasetTrustScore": 0.82, "provenanceDepth": 3, "reproducibilityScore": 0.77},
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_data_product",
    }


def demo_annotation_set(data_product: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "AnnotationSet",
        "id": "urn:srcos:annotation-set:community_truth_demo_labels",
        "subjectRefs": [data_product["id"]],
        "labels": ["factuality", "information-density", "fallacy"],
        "trainingDatasetRef": "urn:srcos:dataset:community_truth_demo_training",
        "evaluationDatasetRef": "urn:srcos:dataset:community_truth_demo_evaluation",
        "annotationReliabilityScore": 0.81,
        "policyRef": "urn:srcos:policy:annotation-training-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_annotations",
    }


def demo_query_run(data_product: dict[str, Any], session_doc: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "QueryRun",
        "queryRunId": "query-run:community-truth-demo:001",
        "dataProductRef": data_product["id"],
        "notebookSessionRef": session_doc["sessionId"],
        "querySurface": "sql",
        "queryText": "SELECT label, count(*) FROM community_truth_demo_annotations GROUP BY label",
        "outputRef": "urn:srcos:artifact:community_truth_demo_query_output",
        "policyRef": "urn:srcos:policy:lattice-query-demo",
    }
    return {**payload, "queryDigest": _digest(payload)}


def demo_promotion_candidate(query_run: dict[str, Any], annotation_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "PromotionCandidate",
        "candidateId": "promotion-candidate:community-truth-demo-model",
        "sourceRefs": [query_run["queryRunId"], annotation_set["id"]],
        "targetKind": "model-candidate",
        "targetRef": "urn:srcos:model:community_truth_demo_candidate",
        "policyRef": "urn:srcos:policy:model-promotion-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_promotion",
    }


def demo_evaluation_bundle(promotion_candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "EvaluationBundle",
        "id": "urn:srcos:evaluation-bundle:community_truth_demo_model_eval",
        "subjectRef": promotion_candidate["targetRef"],
        "evaluationKind": "model",
        "metrics": [
            {"name": "factuality_f1", "value": 0.84, "status": "pass"},
            {"name": "grounding_precision", "value": 0.78, "status": "warn"},
        ],
        "verdict": "needs-review",
        "riskTier": "medium",
        "policyRef": "urn:srcos:policy:model-eval-demo",
        "evidenceRefs": ["urn:srcos:evidence:community_truth_demo_model_eval"],
    }


def demo_factsheet(evaluation_bundle: dict[str, Any], data_product: dict[str, Any], annotation_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "Factsheet",
        "id": "urn:srcos:factsheet:community_truth_demo_model",
        "subjectRef": evaluation_bundle["subjectRef"],
        "factsheetKind": "model",
        "summary": {
            "name": "Community Truth Demo Model",
            "purpose": "Classify factuality and annotation quality for the Lattice demo path.",
            "ownerRef": "urn:srcos:community:lattice-demo",
        },
        "lineageRefs": [data_product["id"], annotation_set["id"]],
        "evaluationRefs": [evaluation_bundle["id"]],
        "approval": {"state": "needs-review", "workflowRef": "urn:srcos:workflow:model-review-demo"},
        "evidenceRefs": ["urn:srcos:evidence:community_truth_demo_factsheet"],
    }


def demo_publication_artifact(factsheet: dict[str, Any], data_product: dict[str, Any], session_doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "PublicationArtifact",
        "id": "urn:srcos:publication-artifact:community_truth_demo_report",
        "title": "Community Truth Demo Reproducible Report",
        "artifactRefs": {
            "dataProductRefs": [data_product["id"]],
            "runtimeRefs": [session_doc["runtimeAssetId"]],
            "notebookRefs": [session_doc["sessionId"]],
            "modelRefs": [factsheet["subjectRef"]],
        },
        "reproduction": {"recipeRef": "urn:srcos:recipe:community_truth_demo_report", "score": 0.74},
        "review": {"state": "under-review", "reviewThreadRefs": ["urn:srcos:review-thread:community_truth_demo_report"]},
        "evidenceRefs": ["urn:srcos:evidence:community_truth_demo_report"],
    }


def demo_product_spine() -> dict[str, Any]:
    catalog_asset = demo_catalog_asset().to_dict()
    runtime_asset = demo_runtime_asset()
    session = create_session(
        project_id="demo-project",
        user_id="demo-user",
        runtime_asset=runtime_asset,
        catalog_inputs=[catalog_asset["catalogAssetId"]],
        policy_ref="urn:srcos:policy:lattice-studio-demo",
    ).to_dict()
    data_product = demo_data_product(catalog_asset)
    annotation_set = demo_annotation_set(data_product)
    query_run = demo_query_run(data_product, session)
    promotion_candidate = demo_promotion_candidate(query_run, annotation_set)
    evaluation_bundle = demo_evaluation_bundle(promotion_candidate)
    factsheet = demo_factsheet(evaluation_bundle, data_product, annotation_set)
    publication = demo_publication_artifact(factsheet, data_product, session)

    records = [
        _record(data_product["id"], "data-product", data_product["name"], "DataProduct", data_product["policyRef"], data_product["evidenceRef"], ["lattice-studio", "lattice-data", "sherlock-search", "slash-topics", "policy-fabric"]),
        _record(annotation_set["id"], "annotation-set", annotation_set["id"], "AnnotationSet", annotation_set["policyRef"], annotation_set["evidenceRef"], ["lattice-studio", "training-dataset", "evaluation-dataset", "governai"]),
        _record(query_run["queryRunId"], "query-run", query_run["queryRunId"], "QueryRun", query_run["policyRef"], query_run["queryDigest"], ["lattice-studio", "federated-query", "sherlock-search"]),
        _record(promotion_candidate["candidateId"], "promotion-candidate", promotion_candidate["candidateId"], "PromotionCandidate", promotion_candidate["policyRef"], promotion_candidate["evidenceRef"], ["lattice-studio", "model-zoo", "governai", "agentplane"]),
        _record(evaluation_bundle["id"], "evaluation-bundle", evaluation_bundle["id"], "EvaluationBundle", evaluation_bundle["policyRef"], evaluation_bundle["evidenceRefs"][0], ["governai", "model-zoo", "policy-fabric"]),
        _record(factsheet["id"], "factsheet", factsheet["id"], "Factsheet", None, factsheet["evidenceRefs"][0], ["governai", "model-zoo", "new-hope"]),
        _record(publication["id"], "publication-artifact", publication["title"], "PublicationArtifact", None, publication["evidenceRefs"][0], ["lattice-studio", "reproducible-publishing", "sherlock-search", "slash-topics"]),
    ]
    record_set = platform_record_set(records)
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeDataGovernAIVerticalDemo",
        "catalogAsset": catalog_asset,
        "runtimeAsset": runtime_asset,
        "notebookSession": session,
        "dataProduct": data_product,
        "annotationSet": annotation_set,
        "queryRun": query_run,
        "promotionCandidate": promotion_candidate,
        "evaluationBundle": evaluation_bundle,
        "factsheet": factsheet,
        "publicationArtifact": publication,
        "platformRecords": record_set,
        "spine": [
            "CatalogAsset",
            "DataProduct",
            "AnnotationSet",
            "RuntimeAsset",
            "NotebookSession",
            "QueryRun",
            "PromotionCandidate",
            "EvaluationBundle",
            "Factsheet",
            "PublicationArtifact",
            "PlatformAssetRecord",
        ],
    }
