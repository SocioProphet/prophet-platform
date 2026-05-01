"""Lattice Model Zoo product-surface fixture.

The model zoo is a governed discovery and promotion surface. It consumes the
Lattice Studio/Data/GovernAI product spine and emits a deterministic model
entry with lineage, runtime, evaluation, factsheet, endpoint, and use-policy
refs. It does not implement a serving backend.
"""

from __future__ import annotations

from typing import Any

from .platform_records import platform_record_set
from .product_spine import demo_product_spine
from .runtime_profiles import RAY_RUNTIME_REF


def demo_model_zoo_entry() -> dict[str, Any]:
    spine = demo_product_spine()
    data_product = spine["dataProduct"]
    evaluation = spine["evaluationBundle"]
    factsheet = spine["factsheet"]

    model_ref = factsheet["subjectRef"]
    endpoint_ref = "urn:srcos:model-endpoint:community_truth_demo_candidate_dry_run"
    use_policy_ref = "urn:srcos:policy:model-use-community-truth-demo"

    model_card = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelCard",
        "id": "urn:srcos:model-card:community_truth_demo_candidate",
        "modelRef": model_ref,
        "name": "Community Truth Demo Model",
        "purpose": "Classify factuality and annotation quality for the Lattice demo path.",
        "ownerRef": "urn:srcos:community:lattice-demo",
        "trainingDataRefs": ["urn:srcos:dataset:community_truth_demo_training", data_product["id"]],
        "evaluationDataRefs": ["urn:srcos:dataset:community_truth_demo_evaluation"],
        "runtimeRef": RAY_RUNTIME_REF,
        "factsheetRef": factsheet["id"],
        "evaluationRefs": [evaluation["id"]],
        "limitations": ["Synthetic demo fixture only", "Not approved for production use"],
    }
    runtime_profile = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelRuntimeProfile",
        "id": "urn:srcos:model-runtime-profile:community_truth_demo_candidate",
        "modelRef": model_ref,
        "runtimeAssetRef": RAY_RUNTIME_REF,
        "servingBackends": ["ray-serve", "kserve", "seldon-core"],
        "defaultServingBackend": "ray-serve",
        "executionMode": "dry-run",
        "policyRef": "urn:srcos:policy:model-runtime-community-truth-demo",
    }
    endpoint = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelEndpoint",
        "id": endpoint_ref,
        "modelRef": model_ref,
        "servingBackend": "ray-serve",
        "route": "/models/community-truth-demo-candidate",
        "state": "candidate-dry-run",
        "runtimeAssetRef": RAY_RUNTIME_REF,
        "policyRef": "urn:srcos:policy:model-endpoint-community-truth-demo",
    }
    use_policy = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelUsePolicy",
        "id": use_policy_ref,
        "modelRef": model_ref,
        "allowedUses": ["evaluation", "demo", "research-review"],
        "forbiddenUses": ["production-decisioning", "unsupervised-export"],
        "requiresApprovalFor": ["promotion", "publication", "external-serving"],
        "policyRef": "urn:srcos:policy:model-eval-demo",
    }
    entry = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelZooEntry",
        "id": "urn:srcos:model-zoo-entry:community_truth_demo_candidate",
        "modelRef": model_ref,
        "name": "Community Truth Demo Candidate",
        "description": "Governed model zoo entry for the Lattice Studio/Data/GovernAI vertical demo.",
        "state": "candidate",
        "dataProductRefs": [data_product["id"]],
        "trainingDatasetRefs": ["urn:srcos:dataset:community_truth_demo_training"],
        "evaluationDatasetRefs": ["urn:srcos:dataset:community_truth_demo_evaluation"],
        "runtimeProfileRef": runtime_profile["id"],
        "runtimeAssetRef": RAY_RUNTIME_REF,
        "endpointRef": endpoint_ref,
        "modelCardRef": model_card["id"],
        "factsheetRef": factsheet["id"],
        "evaluationBundleRefs": [evaluation["id"]],
        "usePolicyRef": use_policy_ref,
        "lineageRefs": [data_product["id"], spine["annotationSet"]["id"], spine["queryRun"]["queryRunId"]],
        "evidenceRefs": ["urn:srcos:evidence:community_truth_demo_model_eval", "urn:srcos:evidence:community_truth_demo_factsheet"],
        "promotionGate": {"state": "needs-review", "workflowRef": "urn:srcos:workflow:model-review-demo"},
    }
    records = platform_record_set([
        {
            "apiVersion": "prophet.socioprophet.dev/v1",
            "kind": "PlatformAssetRecord",
            "assetId": entry["id"],
            "assetKind": "model-zoo-entry",
            "name": entry["name"],
            "version": "0.1.0",
            "sourceApiVersion": "studio.socioprophet.dev/v1",
            "sourceKind": "ModelZooEntry",
            "producerRepo": "SocioProphet/prophet-platform",
            "policyRef": use_policy["policyRef"],
            "evidenceCorrelationId": "urn:srcos:evidence:community_truth_demo_model_eval",
            "promotionChannel": "lattice-data-governai-demo",
            "compatibilitySurfaces": ["lattice-studio", "model-zoo", "ray", "sherlock-search", "slash-topics", "policy-fabric", "agentplane"],
        },
        {
            "apiVersion": "prophet.socioprophet.dev/v1",
            "kind": "PlatformAssetRecord",
            "assetId": endpoint_ref,
            "assetKind": "model-endpoint",
            "name": "Community Truth Demo Candidate Endpoint",
            "version": "0.1.0",
            "sourceApiVersion": "studio.socioprophet.dev/v1",
            "sourceKind": "ModelEndpoint",
            "producerRepo": "SocioProphet/prophet-platform",
            "policyRef": endpoint["policyRef"],
            "evidenceCorrelationId": "urn:srcos:evidence:community_truth_demo_model_endpoint",
            "promotionChannel": "lattice-data-governai-demo",
            "compatibilitySurfaces": ["model-zoo", "ray", "ray-serve", "kserve", "seldon-core", "policy-fabric"],
        },
    ])
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeModelZooFixture",
        "entry": entry,
        "modelCard": model_card,
        "runtimeProfile": runtime_profile,
        "endpoint": endpoint,
        "usePolicy": use_policy,
        "evaluationBundle": evaluation,
        "factsheet": factsheet,
        "platformRecords": records,
    }
