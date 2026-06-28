"""Model Zoo promotion state machine and serving manifest generator for Lattice Studio.

The model zoo entry is a governed discovery surface. Promotion drives it from
candidate-dry-run through extraction, container build, and deployment manifests
for ray-serve, kserve, and seldon-core.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .model_zoo import demo_model_zoo_entry

ServingBackend = str


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ModelZooValidationReport:
    report_id: str
    entry_id: str
    checks: dict[str, bool]
    blocked: bool
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "ModelZooValidationReport",
            "reportId": self.report_id,
            "entryId": self.entry_id,
            "checks": self.checks,
            "blocked": self.blocked,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class ModelZooContainerBuildPlan:
    build_plan_id: str
    entry_id: str
    serving_backend: ServingBackend
    image_ref: str
    base_runtime_ref: str
    sbom_required: bool = True
    signature_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "ModelZooContainerBuildPlan",
            "buildPlanId": self.build_plan_id,
            "entryId": self.entry_id,
            "servingBackend": self.serving_backend,
            "imageRef": self.image_ref,
            "baseRuntimeRef": self.base_runtime_ref,
            "sbomRequired": self.sbom_required,
            "signatureRequired": self.signature_required,
        }


@dataclass(frozen=True)
class ModelZooServingManifest:
    manifest_id: str
    entry_id: str
    serving_backend: ServingBackend
    target_runtime: str
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "ModelZooServingManifest",
            "manifestId": self.manifest_id,
            "entryId": self.entry_id,
            "servingBackend": self.serving_backend,
            "targetRuntime": self.target_runtime,
            "manifest": self.manifest,
        }


def demo_validation_report() -> ModelZooValidationReport:
    fixture = demo_model_zoo_entry()
    entry = fixture["entry"]
    evaluation = fixture["evaluationBundle"]
    factsheet = fixture["factsheet"]
    use_policy = fixture["usePolicy"]
    runtime_profile = fixture["runtimeProfile"]
    endpoint = fixture["endpoint"]

    checks = {
        "evaluation_verdict_not_blocked": evaluation.get("verdict", "pass") != "blocked",
        "factsheet_approved": factsheet.get("state", "approved") == "approved",
        "use_policy_present": bool(use_policy.get("id")),
        "serving_backend_declared": bool(runtime_profile.get("servingBackends")),
        "endpoint_ref_present": bool(entry.get("endpointRef")),
        "lineage_refs_nonempty": bool(entry.get("lineageRefs")),
    }
    blocked = not all(checks.values())
    payload = {"entryId": entry["id"]}
    return ModelZooValidationReport(
        report_id=_digest("model-zoo-validation", payload),
        entry_id=entry["id"],
        checks=checks,
        blocked=blocked,
    )


def build_plans_for_entry(entry: dict[str, Any], runtime_profile: dict[str, Any]) -> list[ModelZooContainerBuildPlan]:
    backends: list[ServingBackend] = runtime_profile.get("servingBackends", [])
    base_runtime_ref = runtime_profile.get("runtimeAssetRef", runtime_profile.get("runtimeRef", ""))
    model_slug = entry["id"].split(":")[-1]
    plans: list[ModelZooContainerBuildPlan] = []
    for backend in backends:
        payload = {"entryId": entry["id"], "servingBackend": backend}
        image_ref = f"ghcr.io/socioprophet/model-zoo/{model_slug}/{backend}:0.1.0"
        plans.append(
            ModelZooContainerBuildPlan(
                build_plan_id=_digest("model-zoo-container-build", payload),
                entry_id=entry["id"],
                serving_backend=backend,
                image_ref=image_ref,
                base_runtime_ref=base_runtime_ref,
            )
        )
    return plans


def _ray_serve_manifest(entry: dict[str, Any], plan: ModelZooContainerBuildPlan, endpoint: dict[str, Any], use_policy: dict[str, Any]) -> dict[str, Any]:
    model_slug = entry["id"].split(":")[-1]
    return {
        "apiVersion": "ray.io/v1alpha1",
        "kind": "RayService",
        "metadata": {
            "name": model_slug.replace("_", "-"),
            "annotations": {"policyRef": use_policy["id"]},
        },
        "spec": {
            "serviceUnhealthySecondThreshold": 300,
            "deploymentUnhealthySecondThreshold": 300,
            "serveConfigV2": {
                "applications": [
                    {
                        "name": model_slug,
                        "import_path": "serve_entrypoint:deployment",
                        "route_prefix": endpoint.get("route", f"/models/{model_slug}"),
                        "runtime_env": {"container": {"image": plan.image_ref}},
                        "deployments": [{"name": model_slug, "num_replicas": 1}],
                    }
                ]
            },
        },
    }


def _kserve_manifest(entry: dict[str, Any], plan: ModelZooContainerBuildPlan, endpoint: dict[str, Any], use_policy: dict[str, Any]) -> dict[str, Any]:
    model_slug = entry["id"].split(":")[-1]
    return {
        "apiVersion": "serving.kserve.io/v1beta1",
        "kind": "InferenceService",
        "metadata": {
            "name": model_slug.replace("_", "-"),
            "annotations": {"policyRef": use_policy["id"]},
        },
        "spec": {
            "predictor": {
                "model": {
                    "modelFormat": {"name": "custom"},
                    "storageUri": f"oci://{plan.image_ref}",
                    "resources": {"requests": {"cpu": "1", "memory": "2Gi"}},
                }
            }
        },
    }


def _seldon_manifest(entry: dict[str, Any], plan: ModelZooContainerBuildPlan, endpoint: dict[str, Any], use_policy: dict[str, Any]) -> dict[str, Any]:
    model_slug = entry["id"].split(":")[-1]
    return {
        "apiVersion": "machinelearning.seldon.io/v1",
        "kind": "SeldonDeployment",
        "metadata": {
            "name": model_slug.replace("_", "-"),
            "annotations": {"policyRef": use_policy["id"]},
        },
        "spec": {
            "predictors": [
                {
                    "name": "default",
                    "replicas": 1,
                    "graph": {
                        "name": model_slug,
                        "type": "MODEL",
                        "implementation": "CUSTOM",
                        "endpoint": {"service_port": 9000},
                    },
                    "componentSpecs": [
                        {
                            "spec": {
                                "containers": [
                                    {
                                        "name": model_slug,
                                        "image": plan.image_ref,
                                    }
                                ]
                            }
                        }
                    ],
                }
            ]
        },
    }


_MANIFEST_BUILDERS = {
    "ray-serve": (_ray_serve_manifest, "kuberay-rayservice"),
    "kserve": (_kserve_manifest, "kserve-inferenceservice"),
    "seldon-core": (_seldon_manifest, "seldon-deployment"),
}


def serving_manifests_for_plans(
    build_plans: list[ModelZooContainerBuildPlan],
    entry: dict[str, Any],
    endpoint: dict[str, Any],
    use_policy: dict[str, Any],
) -> list[ModelZooServingManifest]:
    manifests: list[ModelZooServingManifest] = []
    for plan in build_plans:
        builder, target_runtime = _MANIFEST_BUILDERS.get(
            plan.serving_backend,
            (None, plan.serving_backend),
        )
        if builder is None:
            manifest_dict: dict[str, Any] = {"servingBackend": plan.serving_backend, "imageRef": plan.image_ref}
        else:
            manifest_dict = builder(entry, plan, endpoint, use_policy)
        payload = {"entryId": plan.entry_id, "servingBackend": plan.serving_backend}
        manifests.append(
            ModelZooServingManifest(
                manifest_id=_digest("model-zoo-serving-manifest", payload),
                entry_id=plan.entry_id,
                serving_backend=plan.serving_backend,
                target_runtime=target_runtime,
                manifest=manifest_dict,
            )
        )
    return manifests


def demo_model_zoo_promotion_bundle() -> dict[str, Any]:
    fixture = demo_model_zoo_entry()
    entry = fixture["entry"]
    runtime_profile = fixture["runtimeProfile"]
    endpoint = fixture["endpoint"]
    use_policy = fixture["usePolicy"]

    validation_report = demo_validation_report()
    build_plans = build_plans_for_entry(entry, runtime_profile)
    manifests = serving_manifests_for_plans(build_plans, entry, endpoint, use_policy)

    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelZooPromotionBundle",
        "validationReport": validation_report.to_dict(),
        "containerBuildPlans": [plan.to_dict() for plan in build_plans],
        "servingManifests": [m.to_dict() for m in manifests],
    }


def promotion_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ModelZooPromotionEvidence",
        "promotionDigest": f"sha256:{digest}",
        "buildPlanCount": len(bundle["containerBuildPlans"]),
        "targetRuntimes": sorted({m["targetRuntime"] for m in bundle["servingManifests"]}),
        "evidenceReports": [
            "model-zoo-validation-report",
            "evaluation-verdict-check",
            "factsheet-approval-check",
            "use-policy-binding",
            "container-build-plans",
            "serving-manifests",
            "sbom-required",
            "signature-required",
            "dry-run-only",
        ],
    }


def promotion_to_platform_record(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": "model-zoo-promotion-bundle:lattice-studio-demo",
        "assetKind": "model-zoo-promotion-bundle",
        "name": "lattice-studio-model-zoo-promotion-bundle",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "ModelZooPromotionBundle",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://lattice-studio/model-zoo-promotion",
        "evidenceCorrelationId": "model-zoo-promotion-bundle:lattice-studio-demo",
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "ray-serve",
            "kserve",
            "seldon-core",
            "model-zoo",
            "lattice-studio",
            "sherlock-search",
            "policy-fabric",
            "agentplane",
        ],
    }
