"""Lattice trust and reputation signal fixture.

Trust/reputation signals bridge SocioProphet's source/user/content truth layer
into Lattice data, model, prompt/RAG, evaluation, and publication governance.
This fixture is deterministic and evidence-bearing; it does not implement a
live scoring engine.
"""

from __future__ import annotations

from typing import Any

from .annotation_training import demo_annotation_training_loop
from .model_zoo import demo_model_zoo_entry
from .platform_records import platform_record_set
from .product_spine import demo_product_spine
from .prompt_rag_eval import demo_prompt_rag_eval_lab
from .publication_review import demo_publication_review_package


def demo_trust_reputation_signals() -> dict[str, Any]:
    spine = demo_product_spine()
    annotation = demo_annotation_training_loop()
    model_zoo = demo_model_zoo_entry()
    prompt_rag = demo_prompt_rag_eval_lab()
    publication = demo_publication_review_package()

    signals = [
        _signal(
            "urn:srcos:trust-signal:data-product:community_truth_demo",
            spine["dataProduct"]["id"],
            "DatasetTrustScore",
            0.82,
            {"sourceTrust": 0.84, "licenseCompleteness": 0.9, "lineageDepth": 0.72},
            [spine["dataProduct"]["evidenceRef"]],
        ),
        _signal(
            "urn:srcos:trust-signal:annotation-reliability:community_truth_demo",
            annotation["annotationSet"]["id"],
            "AnnotationReliability",
            annotation["annotationReliabilityScore"]["score"],
            annotation["annotationReliabilityScore"]["components"],
            annotation["annotationReliabilityScore"]["evidenceRefs"],
        ),
        _signal(
            "urn:srcos:trust-signal:model-evaluation-confidence:community_truth_demo",
            model_zoo["entry"]["modelRef"],
            "EvaluationConfidence",
            0.78,
            {"evaluationCoverage": 0.8, "riskTierPenalty": 0.1, "factsheetCompleteness": 0.84},
            model_zoo["entry"]["evidenceRefs"],
        ),
        _signal(
            "urn:srcos:trust-signal:rag-grounding-confidence:community_truth_demo",
            prompt_rag["ragPipeline"]["id"],
            "EvaluationConfidence",
            0.79,
            {"faithfulness": 0.83, "citationCoverage": 0.79, "refusalPrecision": 0.72},
            [prompt_rag["groundingEvaluation"]["evidenceRef"]],
        ),
        _signal(
            "urn:srcos:trust-signal:publication-reproducibility:community_truth_demo",
            publication["researchPackage"]["id"],
            "ReproducibilityScore",
            publication["researchPackage"]["reproducibilityScore"],
            {"recipePresent": 1.0, "attemptStatus": 0.5, "reviewState": 0.4, "citationGraphPresent": 1.0},
            [publication["reproductionAttempt"]["evidenceRef"], publication["citationGraph"]["evidenceRef"]],
        ),
    ]
    posture = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "TrustPostureSummary",
        "id": "urn:srcos:trust-posture:lattice-data-governai-demo",
        "subjectRefs": [signal["subjectRef"] for signal in signals],
        "overallScore": round(sum(signal["score"] for signal in signals) / len(signals), 3),
        "promotionRisk": "medium",
        "policyRef": "urn:srcos:policy:lattice-trust-reputation-demo",
        "evidenceRefs": sorted({evidence for signal in signals for evidence in signal["evidenceRefs"]}),
    }
    records = platform_record_set([
        _record(signal["id"], "trust-signal", f"{signal['signalKind']} for {signal['subjectRef']}", "TrustSignal", posture["policyRef"], signal["evidenceRefs"][0], ["lattice-studio", "governai", "policy-fabric", "sherlock-search"])
        for signal in signals
    ] + [
        _record(posture["id"], "trust-posture-summary", "Lattice Data/GovernAI Trust Posture", "TrustPostureSummary", posture["policyRef"], posture["evidenceRefs"][0], ["lattice-studio", "governai", "policy-fabric", "slash-topics", "new-hope"])
    ])
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeTrustReputationFixture",
        "signals": signals,
        "trustPosture": posture,
        "platformRecords": records,
        "safety": {"fixtureOnly": True, "network": "none", "secrets": "none", "hostMutation": False},
    }


def _signal(signal_id: str, subject_ref: str, signal_kind: str, score: float, components: dict[str, float], evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "TrustSignal",
        "id": signal_id,
        "subjectRef": subject_ref,
        "signalKind": signal_kind,
        "score": score,
        "components": components,
        "evidenceRefs": evidence_refs,
        "policyRef": "urn:srcos:policy:lattice-trust-reputation-demo",
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
