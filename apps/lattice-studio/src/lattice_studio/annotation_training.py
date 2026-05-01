"""Lattice annotation-to-training fixture.

This module turns community/reviewer annotations into governed training and
evaluation dataset candidates. It is a deterministic product-surface fixture;
it does not run model training or own canonical schemas.
"""

from __future__ import annotations

from typing import Any

from .platform_records import platform_record_set
from .product_spine import demo_product_spine


def demo_annotation_training_loop() -> dict[str, Any]:
    spine = demo_product_spine()
    data_product = spine["dataProduct"]
    annotation_set = spine["annotationSet"]
    runtime_ref = "runtime-asset:prophet-python-ml:0.1.0"

    labeling_project = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LabelingProject",
        "id": "urn:srcos:labeling-project:community_truth_demo",
        "name": "Community Truth Demo Labeling Project",
        "dataProductRef": data_product["id"],
        "annotationSetRefs": [annotation_set["id"]],
        "labelTaxonomy": ["factuality", "information-density", "fallacy", "source-quality"],
        "reviewerRefs": ["urn:srcos:user:demo-reviewer"],
        "policyRef": "urn:srcos:policy:annotation-training-demo",
        "licensePolicyRef": data_product["licensePolicyRef"],
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_labeling_project",
    }
    annotation_reliability = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "AnnotationReliabilityScore",
        "id": "urn:srcos:annotation-reliability:community_truth_demo",
        "annotationSetRef": annotation_set["id"],
        "labelingProjectRef": labeling_project["id"],
        "score": 0.81,
        "components": {
            "reviewerReputation": 0.86,
            "interAnnotatorAgreement": 0.78,
            "sourceTrust": 0.82,
            "policyCompleteness": 0.8,
        },
        "evidenceRefs": [annotation_set["evidenceRef"], labeling_project["evidenceRef"]],
    }
    training_dataset = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "TrainingDataset",
        "id": "urn:srcos:dataset:community_truth_demo_training",
        "sourceDataProductRefs": [data_product["id"]],
        "annotationSetRefs": [annotation_set["id"]],
        "labelingProjectRef": labeling_project["id"],
        "split": "train",
        "records": 128,
        "licensePolicyRef": data_product["licensePolicyRef"],
        "trainingAllowed": True,
        "runtimeRef": runtime_ref,
        "qualityProfileRef": data_product["qualityProfileRef"],
        "reliabilityScoreRef": annotation_reliability["id"],
        "policyRef": "urn:srcos:policy:training-dataset-community-truth-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_training_dataset",
    }
    evaluation_dataset = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "EvaluationDataset",
        "id": "urn:srcos:dataset:community_truth_demo_evaluation",
        "sourceDataProductRefs": [data_product["id"]],
        "annotationSetRefs": [annotation_set["id"]],
        "labelingProjectRef": labeling_project["id"],
        "split": "eval",
        "records": 32,
        "licensePolicyRef": data_product["licensePolicyRef"],
        "evaluationAllowed": True,
        "runtimeRef": runtime_ref,
        "qualityProfileRef": data_product["qualityProfileRef"],
        "reliabilityScoreRef": annotation_reliability["id"],
        "policyRef": "urn:srcos:policy:evaluation-dataset-community-truth-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_evaluation_dataset",
    }
    training_recipe = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "TrainingDatasetRecipe",
        "id": "urn:srcos:recipe:community_truth_demo_training_dataset",
        "inputs": [data_product["id"], annotation_set["id"], labeling_project["id"]],
        "outputs": [training_dataset["id"], evaluation_dataset["id"]],
        "steps": [
            "filter-policy-eligible-annotations",
            "deduplicate-targets",
            "split-train-eval",
            "attach-reliability-score",
            "emit-dataset-evidence",
        ],
        "policyRef": "urn:srcos:policy:annotation-training-demo",
        "runtimeRef": runtime_ref,
    }
    consent_use = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "TrainingUsePolicy",
        "id": "urn:srcos:training-use-policy:community_truth_demo",
        "subjectRefs": [training_dataset["id"], evaluation_dataset["id"]],
        "allowedUses": ["demo-training", "evaluation", "research-review"],
        "forbiddenUses": ["external-sale", "production-decisioning", "unattributed-export"],
        "attributionRequired": True,
        "policyRef": "urn:srcos:policy:annotation-training-demo",
    }

    records = platform_record_set([
        _record(labeling_project["id"], "labeling-project", labeling_project["name"], "LabelingProject", labeling_project["policyRef"], labeling_project["evidenceRef"], ["lattice-studio", "annotation-lab", "policy-fabric"]),
        _record(annotation_reliability["id"], "annotation-reliability-score", "Community Truth Annotation Reliability", "AnnotationReliabilityScore", labeling_project["policyRef"], annotation_reliability["evidenceRefs"][0], ["lattice-studio", "governai", "sherlock-search"]),
        _record(training_dataset["id"], "training-dataset", "Community Truth Training Dataset", "TrainingDataset", training_dataset["policyRef"], training_dataset["evidenceRef"], ["lattice-studio", "model-zoo", "ray", "policy-fabric", "sherlock-search"]),
        _record(evaluation_dataset["id"], "evaluation-dataset", "Community Truth Evaluation Dataset", "EvaluationDataset", evaluation_dataset["policyRef"], evaluation_dataset["evidenceRef"], ["lattice-studio", "governai", "evaluation-lab", "policy-fabric", "sherlock-search"]),
        _record(training_recipe["id"], "training-dataset-recipe", "Community Truth Training Dataset Recipe", "TrainingDatasetRecipe", training_recipe["policyRef"], training_dataset["evidenceRef"], ["lattice-studio", "reproducibility", "agentplane"]),
    ])

    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeAnnotationTrainingLoopFixture",
        "dataProduct": data_product,
        "annotationSet": annotation_set,
        "labelingProject": labeling_project,
        "annotationReliabilityScore": annotation_reliability,
        "trainingDataset": training_dataset,
        "evaluationDataset": evaluation_dataset,
        "trainingDatasetRecipe": training_recipe,
        "trainingUsePolicy": consent_use,
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
