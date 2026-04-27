"""Notebook promotion compiler for Lattice Studio.

The notebook is an authoring and provenance surface. Production deployment must
promote extracted, tested, containerized units instead of raw notebooks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

PromotionTarget = Literal[
    "ray-train-job",
    "ray-serve-service",
    "beam-pipeline",
    "paas-service",
    "observable-app",
    "plutojl-job",
    "quarto-publication",
]


@dataclass(frozen=True)
class NotebookExtractionReport:
    report_id: str
    source_notebook_ref: str
    extracted_files: list[str]
    removed_artifacts: list[str]
    checks: dict[str, bool]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "NotebookExtractionReport",
            "reportId": self.report_id,
            "sourceNotebookRef": self.source_notebook_ref,
            "extractedFiles": self.extracted_files,
            "removedArtifacts": self.removed_artifacts,
            "checks": self.checks,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class NotebookPromotionCandidate:
    candidate_id: str
    target: PromotionTarget
    source_notebook_ref: str
    extraction_report_id: str
    entrypoint: str
    input_asset_refs: list[str]
    output_asset_refs: list[str]
    runtime_asset_id: str
    policy_ref: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "NotebookPromotionCandidate",
            "candidateId": self.candidate_id,
            "target": self.target,
            "sourceNotebookRef": self.source_notebook_ref,
            "extractionReportId": self.extraction_report_id,
            "entrypoint": self.entrypoint,
            "inputAssetRefs": self.input_asset_refs,
            "outputAssetRefs": self.output_asset_refs,
            "runtimeAssetId": self.runtime_asset_id,
            "policyRef": self.policy_ref,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class ContainerBuildPlan:
    build_plan_id: str
    candidate_id: str
    image_ref: str
    build_system: str
    base_runtime_ref: str
    command: list[str]
    sbom_required: bool = True
    signature_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "ContainerBuildPlan",
            "buildPlanId": self.build_plan_id,
            "candidateId": self.candidate_id,
            "imageRef": self.image_ref,
            "buildSystem": self.build_system,
            "baseRuntimeRef": self.base_runtime_ref,
            "command": self.command,
            "sbomRequired": self.sbom_required,
            "signatureRequired": self.signature_required,
        }


@dataclass(frozen=True)
class DeploymentTargetPlan:
    deployment_plan_id: str
    candidate_id: str
    target: PromotionTarget
    target_runtime: str
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "DeploymentTargetPlan",
            "deploymentPlanId": self.deployment_plan_id,
            "candidateId": self.candidate_id,
            "target": self.target,
            "targetRuntime": self.target_runtime,
            "manifest": self.manifest,
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_extraction_report() -> NotebookExtractionReport:
    payload = {"sourceNotebookRef": "notebook-session:demo1234567890abcd"}
    return NotebookExtractionReport(
        report_id=_digest("notebook-extraction", payload),
        source_notebook_ref="notebook-session:demo1234567890abcd",
        extracted_files=[
            "src/train.py",
            "src/serve.py",
            "src/pipeline.py",
            "src/app.py",
            "notebooks/report.qmd",
            "observable/demo-dashboard.js",
            "pluto/demo-analysis.jl",
        ],
        removed_artifacts=["stale-cell-outputs", "local-absolute-paths", "exploratory-print-debugging"],
        checks={
            "ordered_cells": True,
            "hidden_state_removed": True,
            "secrets_absent": True,
            "local_paths_parameterized": True,
            "dependencies_locked": True,
            "interfaces_declared": True,
        },
    )


def demo_promotion_candidates(report: NotebookExtractionReport) -> list[NotebookPromotionCandidate]:
    specs: list[tuple[PromotionTarget, str, list[str]]] = [
        ("ray-train-job", "src/train.py", ["catalog://models/demo-classifier@0.2.0"]),
        ("ray-serve-service", "src/serve.py", ["catalog://services/demo-inference-service@0.2.0"]),
        ("beam-pipeline", "src/pipeline.py", ["catalog://datasets/demo-features@0.1.0"]),
        ("paas-service", "src/app.py", ["catalog://applications/demo-notebook-app@0.2.0"]),
        ("observable-app", "observable/demo-dashboard.js", ["catalog://applications/demo-dashboard@0.1.0"]),
        ("plutojl-job", "pluto/demo-analysis.jl", ["catalog://datasets/demo-julia-analysis@0.1.0"]),
        ("quarto-publication", "notebooks/report.qmd", ["catalog://reports/demo-analysis-report@0.1.0"]),
    ]
    candidates: list[NotebookPromotionCandidate] = []
    for target, entrypoint, outputs in specs:
        payload = {"target": target, "entrypoint": entrypoint, "reportId": report.report_id}
        candidates.append(
            NotebookPromotionCandidate(
                candidate_id=_digest("notebook-promotion", payload),
                target=target,
                source_notebook_ref=report.source_notebook_ref,
                extraction_report_id=report.report_id,
                entrypoint=entrypoint,
                input_asset_refs=["catalog://datasets/demo-csv@0.1.0", "catalog://models/demo-classifier@0.1.0"],
                output_asset_refs=outputs,
                runtime_asset_id="runtime-asset:prophet-python-ml:0.1.0",
                policy_ref="policy://lattice-studio/notebook-promotion",
            )
        )
    return candidates


def build_plan_for_candidate(candidate: NotebookPromotionCandidate) -> ContainerBuildPlan:
    payload = {"candidateId": candidate.candidate_id, "target": candidate.target}
    image_ref = f"ghcr.io/socioprophet/lattice-studio/{candidate.target}:0.1.0"
    return ContainerBuildPlan(
        build_plan_id=_digest("container-build", payload),
        candidate_id=candidate.candidate_id,
        image_ref=image_ref,
        build_system="nix-oci",
        base_runtime_ref=candidate.runtime_asset_id,
        command=["python", candidate.entrypoint] if candidate.entrypoint.endswith(".py") else ["run", candidate.entrypoint],
    )


def deployment_plan_for_candidate(candidate: NotebookPromotionCandidate) -> DeploymentTargetPlan:
    target_runtime = {
        "ray-train-job": "kuberay-rayjob",
        "ray-serve-service": "kuberay-rayservice",
        "beam-pipeline": "beam-runner",
        "paas-service": "kubernetes-paas",
        "observable-app": "browser-static-app",
        "plutojl-job": "julia-container-job",
        "quarto-publication": "quarto-render-publish",
    }[candidate.target]
    manifest = {
        "entrypoint": candidate.entrypoint,
        "inputs": candidate.input_asset_refs,
        "outputs": candidate.output_asset_refs,
        "policyRef": candidate.policy_ref,
        "dryRun": True,
    }
    return DeploymentTargetPlan(
        deployment_plan_id=_digest("deployment-target", {"candidateId": candidate.candidate_id, "runtime": target_runtime}),
        candidate_id=candidate.candidate_id,
        target=candidate.target,
        target_runtime=target_runtime,
        manifest=manifest,
    )


def demo_notebook_promotion_bundle() -> dict[str, Any]:
    report = demo_extraction_report()
    candidates = demo_promotion_candidates(report)
    build_plans = [build_plan_for_candidate(candidate) for candidate in candidates]
    deployment_plans = [deployment_plan_for_candidate(candidate) for candidate in candidates]
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "NotebookPromotionBundle",
        "extractionReport": report.to_dict(),
        "promotionCandidates": [candidate.to_dict() for candidate in candidates],
        "containerBuildPlans": [plan.to_dict() for plan in build_plans],
        "deploymentTargetPlans": [plan.to_dict() for plan in deployment_plans],
    }


def promotion_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "NotebookPromotionEvidence",
        "promotionDigest": f"sha256:{digest}",
        "candidateCount": len(bundle["promotionCandidates"]),
        "targetRuntimes": sorted({plan["targetRuntime"] for plan in bundle["deploymentTargetPlans"]}),
        "evidenceReports": [
            "notebook-extraction-report",
            "junk-removal-checks",
            "container-build-plans",
            "deployment-target-plans",
            "policy-binding",
            "catalog-input-output-binding",
            "dry-run-only",
        ],
    }


def promotion_to_platform_record(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": "notebook-promotion-bundle:lattice-studio-demo",
        "assetKind": "notebook-promotion-bundle",
        "name": "lattice-studio-notebook-promotion-bundle",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "NotebookPromotionBundle",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://lattice-studio/notebook-promotion",
        "evidenceCorrelationId": "notebook-promotion-bundle:lattice-studio-demo",
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "ray-train",
            "ray-serve",
            "beam",
            "paas",
            "observable",
            "plutojl",
            "quarto",
            "datahub",
            "sherlock-search",
        ],
    }
