"""End-to-end Lattice Studio demo readiness fixture.

The fixture composes the existing deterministic Lattice Studio/Data/GovernAI
product surfaces into a single readiness report. It does not launch services or
execute models; it proves that the public demo path has coherent refs, gates,
runtime role bindings, evidence, and shell-facing command targets.
"""

from __future__ import annotations

from typing import Any

from .active_metadata import demo_active_metadata_spine
from .annotation_training import demo_annotation_training_loop
from .model_zoo import demo_model_zoo_entry
from .product_spine import demo_product_spine
from .prompt_rag_eval import demo_prompt_rag_eval_lab
from .publication_review import demo_publication_review_package
from .runtime_profiles import BEAM_RUNTIME_REF, NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF, demo_runtime_profile_catalog
from .trust_reputation import demo_trust_reputation_signals


REQUIRED_ESTATE_REFS = {
    "schema": "SourceOS-Linux/sourceos-spec#75",
    "runtimeProfiles": "SocioProphet/lattice-forge#11",
    "runtimePromotionManifest": "SocioProphet/lattice-forge#12",
    "runtimeProfileCatalog": "SocioProphet/prophet-platform#306",
    "mlopsRuntimeExecution": "SocioProphet/prophet-platform-fabric-mlops-ts-suite#34",
    "agentplaneRuntimeRefs": "SocioProphet/agentplane#77",
    "sherlockRuntimeIndex": "SocioProphet/sherlock-search#32",
    "slashRuntimeTopics": "SocioProphet/slash-topics#25",
    "newHopeRuntimeMembrane": "SocioProphet/new-hope#9",
    "policyRuntimePromotion": "SocioProphet/policy-fabric#42",
    "cloudshellRuntimeRoutes": "SocioProphet/cloudshell-fog#31",
    "topologyRuntimePromotion": "SocioProphet/sociosphere#243",
}


def demo_readiness_report() -> dict[str, Any]:
    product_spine = demo_product_spine()
    runtime_catalog = demo_runtime_profile_catalog()
    annotation_training = demo_annotation_training_loop()
    model_zoo = demo_model_zoo_entry()
    prompt_rag = demo_prompt_rag_eval_lab()
    publication_review = demo_publication_review_package()
    active_metadata = demo_active_metadata_spine()
    trust = demo_trust_reputation_signals()

    checks = [
        _check("data-product", product_spine["dataProduct"]["id"], True, [product_spine["dataProduct"]["policyRef"], product_spine["dataProduct"]["evidenceRef"]]),
        _check("runtime-profile-catalog", runtime_catalog["sourceRef"], _runtime_catalog_ready(runtime_catalog), list(runtime_catalog["runtimeRefs"].values()) if "runtimeRefs" in runtime_catalog else [NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF, BEAM_RUNTIME_REF]),
        _check("annotation-to-training", annotation_training["trainingDataset"]["id"], _annotation_training_ready(annotation_training), [annotation_training["trainingDataset"]["runtimeRef"], annotation_training["trainingDataset"]["trainingRuntimeRef"]]),
        _check("model-zoo", model_zoo["entry"]["id"], _model_zoo_ready(model_zoo), [model_zoo["entry"]["runtimeAssetRef"], model_zoo["entry"]["factsheetRef"]]),
        _check("prompt-rag-eval", prompt_rag["ragPipeline"]["id"], _prompt_rag_ready(prompt_rag), [prompt_rag["ragPipeline"]["runtimeRef"], prompt_rag["ragPipeline"]["retrievalRuntimeRef"]]),
        _check("publication-review", publication_review["researchPackage"]["id"], _publication_review_ready(publication_review), [publication_review["reviewDecision"]["id"], publication_review["reproductionAttempt"]["id"]]),
        _check("active-metadata", active_metadata["routing"]["searchConsumer"], _active_metadata_ready(active_metadata), list(active_metadata["routing"].values())),
        _check("trust-reputation", trust["trustPosture"]["id"], _trust_ready(trust), trust["trustPosture"]["evidenceRefs"]),
        _check("policy-governance", REQUIRED_ESTATE_REFS["policyRuntimePromotion"], True, [REQUIRED_ESTATE_REFS["policyRuntimePromotion"]]),
        _check("developer-home", REQUIRED_ESTATE_REFS["cloudshellRuntimeRoutes"], True, [REQUIRED_ESTATE_REFS["cloudshellRuntimeRoutes"], REQUIRED_ESTATE_REFS["agentplaneRuntimeRefs"]]),
    ]
    blockers = _blockers(checks)
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeDemoReadinessReport",
        "metadata": {
            "name": "lattice-studio-data-governai-demo-readiness",
            "version": "0.1.0",
            "generatedBy": "lattice_studio.demo_readiness.demo_readiness_report",
        },
        "estateRefs": REQUIRED_ESTATE_REFS,
        "runtimeRefs": {
            "notebookRuntimeRef": NOTEBOOK_RUNTIME_REF,
            "rayRuntimeRef": RAY_RUNTIME_REF,
            "beamRuntimeRef": BEAM_RUNTIME_REF,
            "runtimeProfileBindingRef": "runtime-profile-binding:lattice-data-governai:0.1.0",
            "runtimePromotionManifestRef": "runtime-promotion-manifest:lattice-runtime-promotion-manifest:0.1.0",
        },
        "demoPath": [
            "catalog-search",
            "data-product-inspection",
            "runtime-profile-selection",
            "notebook-launch-dry-run",
            "annotation-to-training",
            "ray-model-dry-run",
            "beam-quality-dry-run",
            "model-zoo-review",
            "prompt-rag-evaluation",
            "publication-review-and-reproduction",
            "active-metadata-indexing",
            "trust-posture-review",
        ],
        "checks": checks,
        "readiness": {
            "state": "demo-ready" if not blockers else "blocked",
            "blockers": blockers,
            "stableRuntimePromotion": "blocked-pending-external-evidence",
            "devRuntimePromotion": "allowed-with-generated-evidence",
            "network": "none",
            "secrets": "none",
            "hostMutation": False,
        },
        "shellCommands": [
            "/lattice data search community_truth_demo",
            "/lattice runtime pick prophet-python-ml",
            "/lattice runtime pick prophet-ray-ml",
            "/lattice runtime pick prophet-beam-dataops",
            "/lattice notebook launch community_truth_demo --runtime prophet-python-ml",
            "/lattice mlops ray run community_truth_demo --runtime prophet-ray-ml --dry-run",
            "/lattice dataops beam run community_truth_demo --runtime prophet-beam-dataops --dry-run",
            "/lattice govern review urn:srcos:evaluation-bundle:community_truth_demo_model_eval",
            "/lattice publication inspect urn:srcos:publication-artifact:community_truth_demo_report",
        ],
    }


def _check(name: str, subject_ref: str, passed: bool, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "subjectRef": subject_ref,
        "passed": passed,
        "evidenceRefs": evidence_refs,
    }


def _blockers(checks: list[dict[str, Any]]) -> list[str]:
    return [check["name"] for check in checks if not check["passed"]]


def _runtime_catalog_ready(catalog: dict[str, Any]) -> bool:
    bindings = catalog["roleBindings"]
    return (
        catalog["defaultNotebookRuntimeRef"] == NOTEBOOK_RUNTIME_REF
        and catalog["defaultRayRuntimeRef"] == RAY_RUNTIME_REF
        and catalog["defaultBeamRuntimeRef"] == BEAM_RUNTIME_REF
        and bindings["NotebookSession"] == NOTEBOOK_RUNTIME_REF
        and bindings["ModelZooEntry"] == RAY_RUNTIME_REF
        and bindings["BeamPipelineDryRunPlan"] == BEAM_RUNTIME_REF
    )


def _annotation_training_ready(fixture: dict[str, Any]) -> bool:
    return (
        fixture["trainingDataset"]["runtimeRef"] == BEAM_RUNTIME_REF
        and fixture["trainingDataset"]["trainingRuntimeRef"] == RAY_RUNTIME_REF
        and fixture["evaluationDataset"]["runtimeRef"] == BEAM_RUNTIME_REF
        and fixture["evaluationDataset"]["evaluationRuntimeRef"] == RAY_RUNTIME_REF
        and fixture["trainingUsePolicy"]["attributionRequired"] is True
    )


def _model_zoo_ready(fixture: dict[str, Any]) -> bool:
    return (
        fixture["entry"]["runtimeAssetRef"] == RAY_RUNTIME_REF
        and fixture["runtimeProfile"]["runtimeAssetRef"] == RAY_RUNTIME_REF
        and fixture["endpoint"]["runtimeAssetRef"] == RAY_RUNTIME_REF
        and fixture["entry"]["promotionGate"]["state"] == "needs-review"
    )


def _prompt_rag_ready(fixture: dict[str, Any]) -> bool:
    return (
        fixture["ragPipeline"]["runtimeRef"] == RAY_RUNTIME_REF
        and fixture["ragPipeline"]["retrievalRuntimeRef"] == BEAM_RUNTIME_REF
        and fixture["evaluationBundle"]["verdict"] == "needs-review"
        and fixture["regressionGate"]["blocksPromotion"] is True
    )


def _publication_review_ready(fixture: dict[str, Any]) -> bool:
    return (
        fixture["researchPackage"]["state"] == "under-review"
        and fixture["reviewDecision"]["state"] == "needs-revision"
        and fixture["reproductionAttempt"]["status"] == "partial-pass"
    )


def _active_metadata_ready(fixture: dict[str, Any]) -> bool:
    routing = fixture["routing"]
    return all(key in routing for key in ["searchConsumer", "topicConsumer", "semanticMembraneConsumer", "policyConsumer", "topologyConsumer"])


def _trust_ready(fixture: dict[str, Any]) -> bool:
    return fixture["trustPosture"]["promotionRisk"] == "medium" and bool(fixture["trustPosture"]["evidenceRefs"])
