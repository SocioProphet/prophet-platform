"""Lattice reproducible publication and peer-review fixture.

This module promotes the existing Product Spine publication artifact into a
reproducible research package with review, citation, and reproduction records.
It is a deterministic product-surface fixture only.
"""

from __future__ import annotations

from typing import Any

from .platform_records import platform_record_set
from .product_spine import demo_product_spine


def demo_publication_review_package() -> dict[str, Any]:
    spine = demo_product_spine()
    data_product = spine["dataProduct"]
    runtime_asset = spine["runtimeAsset"]
    notebook_session = spine["notebookSession"]
    evaluation = spine["evaluationBundle"]
    factsheet = spine["factsheet"]
    publication = spine["publicationArtifact"]

    runtime_ref = "runtime-asset:prophet-python-ml:0.1.0"
    publication_ref = publication["id"]
    research_package_ref = "urn:srcos:research-package:community_truth_demo_report"
    review_thread_ref = "urn:srcos:review-thread:community_truth_demo_report"
    citation_graph_ref = "urn:srcos:citation-graph:community_truth_demo_report"
    reproduction_attempt_ref = "urn:srcos:reproduction-attempt:community_truth_demo_report_001"

    research_package = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ResearchPackage",
        "id": research_package_ref,
        "publicationArtifactRef": publication_ref,
        "title": publication["title"],
        "dataProductRefs": [data_product["id"]],
        "runtimeRefs": [runtime_ref],
        "notebookRefs": [notebook_session["sessionId"]],
        "modelRefs": [factsheet["subjectRef"]],
        "evaluationBundleRefs": [evaluation["id"]],
        "factsheetRefs": [factsheet["id"]],
        "evidenceRefs": publication["evidenceRefs"] + evaluation["evidenceRefs"] + factsheet["evidenceRefs"],
        "reviewThreadRefs": [review_thread_ref],
        "citationGraphRef": citation_graph_ref,
        "reproductionRecipeRef": publication["reproduction"]["recipeRef"],
        "reproducibilityScore": publication["reproduction"]["score"],
        "policyRef": "urn:srcos:policy:publication-review-demo",
        "state": "under-review",
    }
    review_thread = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ReviewThread",
        "id": review_thread_ref,
        "publicationArtifactRef": publication_ref,
        "researchPackageRef": research_package_ref,
        "state": "under-review",
        "reviewerRefs": ["urn:srcos:user:demo-reviewer"],
        "comments": [
            {
                "id": "review-comment:community-truth-demo:001",
                "authorRef": "urn:srcos:user:demo-reviewer",
                "body": "Reproduction package is complete enough for fixture review; citation coverage remains warning-level.",
                "evidenceRefs": ["urn:srcos:evidence:community_truth_demo_grounding_eval"],
            }
        ],
        "policyRef": "urn:srcos:policy:publication-review-demo",
    }
    review_decision = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ReviewDecision",
        "id": "urn:srcos:review-decision:community_truth_demo_report",
        "publicationArtifactRef": publication_ref,
        "reviewThreadRef": review_thread_ref,
        "state": "needs-revision",
        "because": [
            "publication.status=under-review",
            "citation_coverage=warn",
            "model factsheet approval=needs-review",
        ],
        "policyRef": "urn:srcos:policy:publication-review-demo",
    }
    citation_graph = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "CitationGraph",
        "id": citation_graph_ref,
        "publicationArtifactRef": publication_ref,
        "nodes": [
            {"id": data_product["id"], "kind": "DataProduct"},
            {"id": evaluation["id"], "kind": "EvaluationBundle"},
            {"id": factsheet["id"], "kind": "Factsheet"},
        ],
        "edges": [
            {"from": publication_ref, "to": data_product["id"], "rel": "uses-data"},
            {"from": publication_ref, "to": evaluation["id"], "rel": "supported-by-evaluation"},
            {"from": publication_ref, "to": factsheet["id"], "rel": "describes-model"},
        ],
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_citation_graph",
    }
    reproduction_attempt = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ReproductionAttempt",
        "id": reproduction_attempt_ref,
        "researchPackageRef": research_package_ref,
        "recipeRef": research_package["reproductionRecipeRef"],
        "runtimeRef": runtime_ref,
        "inputRefs": [data_product["id"], notebook_session["sessionId"], evaluation["id"]],
        "outputRefs": [publication_ref, citation_graph_ref],
        "status": "partial-pass",
        "verified": False,
        "because": ["citation coverage is below promotion threshold", "review decision requires revision"],
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_reproduction_attempt_001",
    }

    records = platform_record_set([
        _record(research_package_ref, "research-package", research_package["title"], "ResearchPackage", research_package["policyRef"], research_package["evidenceRefs"][0], ["lattice-studio", "reproducible-publishing", "sherlock-search", "slash-topics", "policy-fabric"]),
        _record(review_thread_ref, "review-thread", "Community Truth Demo Review Thread", "ReviewThread", review_thread["policyRef"], review_thread["comments"][0]["evidenceRefs"][0], ["lattice-studio", "review-workflow", "policy-fabric"]),
        _record(citation_graph_ref, "citation-graph", "Community Truth Demo Citation Graph", "CitationGraph", research_package["policyRef"], citation_graph["evidenceRef"], ["lattice-studio", "knowledge-graph", "sherlock-search"]),
        _record(reproduction_attempt_ref, "reproduction-attempt", "Community Truth Demo Reproduction Attempt", "ReproductionAttempt", research_package["policyRef"], reproduction_attempt["evidenceRef"], ["lattice-studio", "reproducible-publishing", "agentplane", "policy-fabric"]),
    ])

    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticePublicationReviewFixture",
        "publicationArtifact": publication,
        "researchPackage": research_package,
        "reviewThread": review_thread,
        "reviewDecision": review_decision,
        "citationGraph": citation_graph,
        "reproductionAttempt": reproduction_attempt,
        "runtimeAsset": runtime_asset,
        "evaluationBundle": evaluation,
        "factsheet": factsheet,
        "platformRecords": records,
    }


def _record(asset_id: str, asset_kind: str, name: str, source_kind: str, policy_ref: str, evidence_ref: str, surfaces: list[str]) -> dict[str, Any]:
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
        "evidenceCorrelationId": evidence_ref,
        "promotionChannel": "lattice-data-governai-demo",
        "compatibilitySurfaces": surfaces,
    }
