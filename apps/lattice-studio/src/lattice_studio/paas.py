"""PaaS DevOps lane for Lattice Studio.

This models a Cloud Foundry-style developer experience over Kubernetes:
source/application/service input, build mode, environment, routing, observability,
rollback, policy, and evidence. It is side-effect-free in this tranche; deploy
execution can later target Porter-style PaaS, Kubernetes, Helm, or internal zone
publication brokers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

BuildMode = Literal["buildpack", "dockerfile", "oci-image", "helm-chart"]
DeploymentKind = Literal["application", "service", "notebook-app", "agent-service"]
EnvironmentKind = Literal["local-sourceos", "preview", "dev", "staging", "production"]


@dataclass(frozen=True)
class PaaSDeploymentPlan:
    deployment_id: str
    name: str
    kind: DeploymentKind
    source_ref: str
    build_mode: BuildMode
    runtime_asset_id: str | None
    catalog_asset_refs: list[str]
    environment: EnvironmentKind
    target_platform: str
    route: str | None
    policy_ref: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "PaaSDeploymentPlan",
            "deploymentId": self.deployment_id,
            "name": self.name,
            "deploymentKind": self.kind,
            "sourceRef": self.source_ref,
            "buildMode": self.build_mode,
            "runtimeAssetId": self.runtime_asset_id,
            "catalogAssetRefs": self.catalog_asset_refs,
            "environment": self.environment,
            "targetPlatform": self.target_platform,
            "route": self.route,
            "policyRef": self.policy_ref,
            "createdAt": self.created_at,
            "capabilities": [
                "gitops-source-binding",
                "kubernetes-targeting",
                "preview-environment",
                "logs-metrics-rollbacks",
                "policy-gated-promotion",
                "evidence-emission",
            ],
        }


def create_deployment_plan(
    *,
    name: str,
    kind: DeploymentKind,
    source_ref: str,
    build_mode: BuildMode,
    runtime_asset_id: str | None,
    catalog_asset_refs: list[str] | None,
    environment: EnvironmentKind,
    target_platform: str,
    route: str | None,
    policy_ref: str | None,
) -> PaaSDeploymentPlan:
    seed = json.dumps(
        {
            "name": name,
            "kind": kind,
            "sourceRef": source_ref,
            "buildMode": build_mode,
            "environment": environment,
            "targetPlatform": target_platform,
            "route": route,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return PaaSDeploymentPlan(
        deployment_id="paas-deployment:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        name=name,
        kind=kind,
        source_ref=source_ref,
        build_mode=build_mode,
        runtime_asset_id=runtime_asset_id,
        catalog_asset_refs=sorted(catalog_asset_refs or []),
        environment=environment,
        target_platform=target_platform,
        route=route,
        policy_ref=policy_ref,
    )


def deployment_evidence(plan: PaaSDeploymentPlan) -> dict[str, Any]:
    doc = plan.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "PaaSDeploymentEvidence",
        "deploymentId": plan.deployment_id,
        "deploymentKind": plan.kind,
        "environment": plan.environment,
        "targetPlatform": plan.target_platform,
        "deploymentDigest": f"sha256:{digest}",
        "evidenceReports": [
            "source-binding",
            "build-mode",
            "runtime-binding",
            "catalog-asset-binding",
            "target-platform",
            "route-binding",
            "policy-binding",
            "rollback-capability",
            "logs-metrics-capability",
        ],
    }


def deployment_to_platform_record(plan: PaaSDeploymentPlan) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plan.deployment_id,
        "assetKind": f"paas-{plan.kind}",
        "name": plan.name,
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "PaaSDeploymentPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": plan.policy_ref,
        "evidenceCorrelationId": plan.deployment_id,
        "promotionChannel": plan.environment,
        "compatibilitySurfaces": [
            "lattice-studio",
            "porter-paas-devops",
            "kubernetes",
            "sourceos-local",
            "agentplane",
            "cloudshell-fog",
        ],
    }
