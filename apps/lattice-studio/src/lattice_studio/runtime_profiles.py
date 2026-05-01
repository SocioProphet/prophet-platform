"""Lattice runtime profile catalog fixture.

This module records the runtime-role split created in `SocioProphet/lattice-forge#11`.
The platform should no longer treat `prophet-python-ml` as the only usable
RuntimeAsset. Notebook work uses the base Python profile, model training/serving
uses the Ray profile, and Beam/DataOps uses the Beam profile.
"""

from __future__ import annotations

from typing import Any

from .platform_records import platform_record_set

NOTEBOOK_RUNTIME_REF = "runtime-asset:prophet-python-ml:0.1.0"
RAY_RUNTIME_REF = "runtime-asset:prophet-ray-ml:0.1.0"
BEAM_RUNTIME_REF = "runtime-asset:prophet-beam-dataops:0.1.0"


def demo_runtime_profile_catalog() -> dict[str, Any]:
    profiles = [
        _profile(
            name="prophet-python-ml",
            runtime_ref=NOTEBOOK_RUNTIME_REF,
            runtime_class="notebook",
            roles=["notebook-session", "query-run", "prompt-authoring", "publication-reproduction"],
            surfaces=["jupyter", "jupyterlab", "lattice-studio", "prophet-platform", "agentplane"],
            evidence_ref="urn:srcos:evidence:runtime-prophet-python-ml-demo",
            policy_ref="policy://runtime/prophet-python-ml-demo",
        ),
        _profile(
            name="prophet-ray-ml",
            runtime_ref=RAY_RUNTIME_REF,
            runtime_class="ray",
            roles=["ray-train", "ray-serve", "model-zoo", "model-evaluation"],
            surfaces=["lattice-studio", "ray", "model-zoo", "agentplane", "prophet-platform"],
            evidence_ref="urn:srcos:evidence:runtime-prophet-ray-ml-demo",
            policy_ref="policy://runtime/prophet-ray-ml-demo",
        ),
        _profile(
            name="prophet-beam-dataops",
            runtime_ref=BEAM_RUNTIME_REF,
            runtime_class="beam",
            roles=["beam-pipeline", "data-quality", "dataset-build", "lineage-run"],
            surfaces=["lattice-studio", "beam", "data-quality", "agentplane", "prophet-platform"],
            evidence_ref="urn:srcos:evidence:runtime-prophet-beam-dataops-demo",
            policy_ref="policy://runtime/prophet-beam-dataops-demo",
        ),
    ]
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeRuntimeProfileCatalogFixture",
        "sourceRef": "SocioProphet/lattice-forge#11",
        "defaultNotebookRuntimeRef": NOTEBOOK_RUNTIME_REF,
        "defaultRayRuntimeRef": RAY_RUNTIME_REF,
        "defaultBeamRuntimeRef": BEAM_RUNTIME_REF,
        "profiles": profiles,
        "roleBindings": {
            "NotebookSession": NOTEBOOK_RUNTIME_REF,
            "QueryRun": NOTEBOOK_RUNTIME_REF,
            "ModelZooEntry": RAY_RUNTIME_REF,
            "ModelRuntimeProfile": RAY_RUNTIME_REF,
            "ModelEndpoint": RAY_RUNTIME_REF,
            "RayJobDryRunPlan": RAY_RUNTIME_REF,
            "BeamPipelineDryRunPlan": BEAM_RUNTIME_REF,
            "TrainingDatasetRecipe": BEAM_RUNTIME_REF,
            "QualityProfile": BEAM_RUNTIME_REF,
            "PublicationArtifact": NOTEBOOK_RUNTIME_REF,
        },
        "platformRecords": platform_record_set([
            _record(profile) for profile in profiles
        ]),
    }


def _profile(name: str, runtime_ref: str, runtime_class: str, roles: list[str], surfaces: list[str], evidence_ref: str, policy_ref: str) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "RuntimeProfileBinding",
        "name": name,
        "runtimeAssetRef": runtime_ref,
        "runtimeClass": runtime_class,
        "roles": roles,
        "compatibilitySurfaces": surfaces,
        "policyRef": policy_ref,
        "evidenceRef": evidence_ref,
    }


def _record(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": profile["runtimeAssetRef"],
        "assetKind": "runtime-profile-binding",
        "name": profile["name"],
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "RuntimeProfileBinding",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": profile["policyRef"],
        "evidenceCorrelationId": profile["evidenceRef"],
        "promotionChannel": "lattice-data-governai-demo",
        "compatibilitySurfaces": sorted(set(profile["compatibilitySurfaces"] + ["sherlock-search", "slash-topics", "policy-fabric"])),
    }
