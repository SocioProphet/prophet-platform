"""Bring-your-own-cloud compatibility contracts for Lattice Studio.

BYOC support must be provider-neutral across storage, compute, and I/O. It also
needs a local/fog terminal surface. CloudShell Fog provides that local/fog shell
lane through OIDC, placement, policy profiles, WebSocket PTY, Kubernetes/stub
connectors, audit events, OpenTelemetry, Argo CD, and Tekton Chains.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

StorageKind = Literal["s3-compatible", "azure-blob", "gcs", "posix", "nfs", "minio", "lakehouse"]
ComputeKind = Literal["kubernetes", "array-cluster", "ray-cluster", "spark-cluster", "edge-node", "local-sourceos"]
IOKind = Literal["object-store", "posix-mount", "websocket-pty", "kafka", "http-api", "jdbc", "arrow-flight"]


@dataclass(frozen=True)
class BYOCStorageProfile:
    profile_id: str
    kind: StorageKind
    endpoint_ref: str
    credential_ref: str
    sovereignty_zone: str
    data_residency: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profileId": self.profile_id,
            "kind": self.kind,
            "endpointRef": self.endpoint_ref,
            "credentialRef": self.credential_ref,
            "sovereigntyZone": self.sovereignty_zone,
            "dataResidency": self.data_residency,
        }


@dataclass(frozen=True)
class BYOCComputeTarget:
    target_id: str
    kind: ComputeKind
    cluster_ref: str
    scheduler_ref: str
    accelerator_profile: str
    trust_tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "targetId": self.target_id,
            "kind": self.kind,
            "clusterRef": self.cluster_ref,
            "schedulerRef": self.scheduler_ref,
            "acceleratorProfile": self.accelerator_profile,
            "trustTier": self.trust_tier,
        }


@dataclass(frozen=True)
class BYOCIOBinding:
    binding_id: str
    kind: IOKind
    source_ref: str
    sink_ref: str
    policy_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bindingId": self.binding_id,
            "kind": self.kind,
            "sourceRef": self.source_ref,
            "sinkRef": self.sink_ref,
            "policyRef": self.policy_ref,
        }


@dataclass(frozen=True)
class CloudShellFogBinding:
    binding_id: str
    repo_ref: str
    session_api_ref: str
    websocket_pty_ref: str
    placement_mode: str
    policy_profile: str
    runtime_connector: str
    audit_ref: str
    telemetry_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bindingId": self.binding_id,
            "repoRef": self.repo_ref,
            "sessionApiRef": self.session_api_ref,
            "websocketPtyRef": self.websocket_pty_ref,
            "placementMode": self.placement_mode,
            "policyProfile": self.policy_profile,
            "runtimeConnector": self.runtime_connector,
            "auditRef": self.audit_ref,
            "telemetryRef": self.telemetry_ref,
            "capabilities": [
                "oidc-authentication",
                "fog-first-placement",
                "cloud-fallback",
                "yaml-policy-profiles",
                "websocket-pty",
                "kubernetes-runtime-connector",
                "stub-runtime-connector",
                "audit-events",
                "opentelemetry",
                "argocd-gitops",
                "tekton-chains-supply-chain",
            ],
        }


@dataclass(frozen=True)
class BYOCPlacementPlan:
    plan_id: str
    storage_profiles: list[BYOCStorageProfile]
    compute_targets: list[BYOCComputeTarget]
    io_bindings: list[BYOCIOBinding]
    cloudshell_fog: CloudShellFogBinding
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "BYOCPlacementPlan",
            "planId": self.plan_id,
            "storageProfiles": [profile.to_dict() for profile in self.storage_profiles],
            "computeTargets": [target.to_dict() for target in self.compute_targets],
            "ioBindings": [binding.to_dict() for binding in self.io_bindings],
            "cloudShellFog": self.cloudshell_fog.to_dict(),
            "createdAt": self.created_at,
            "designRule": "Storage, compute, and I/O placement must be provider-neutral and able to run near governed data.",
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_byoc_placement_plan() -> BYOCPlacementPlan:
    storage = [
        BYOCStorageProfile(
            profile_id="storage:s3-compatible-demo",
            kind="s3-compatible",
            endpoint_ref="s3://byoc-demo-bucket",
            credential_ref="secret://byoc/s3/demo",
            sovereignty_zone="customer-controlled",
            data_residency="us-east-demo",
        ),
        BYOCStorageProfile(
            profile_id="storage:posix-local-demo",
            kind="posix",
            endpoint_ref="file:///workspace/data",
            credential_ref="local://sourceos/session",
            sovereignty_zone="local-sourceos",
            data_residency="edge-local",
        ),
    ]
    compute = [
        BYOCComputeTarget(
            target_id="compute:kubernetes-demo",
            kind="kubernetes",
            cluster_ref="k8s://customer-cluster/dev",
            scheduler_ref="kubernetes/default-scheduler",
            accelerator_profile="cpu-standard",
            trust_tier="trusted-cloud-or-region",
        ),
        BYOCComputeTarget(
            target_id="compute:array-demo",
            kind="array-cluster",
            cluster_ref="array://training-cluster/demo",
            scheduler_ref="array/ray-scheduler",
            accelerator_profile="gpu-optional",
            trust_tier="customer-controlled-compute",
        ),
        BYOCComputeTarget(
            target_id="compute:sourceos-local-demo",
            kind="local-sourceos",
            cluster_ref="sourceos://local/workbench",
            scheduler_ref="local/sourceos-runner",
            accelerator_profile="cpu-local",
            trust_tier="local-edge",
        ),
    ]
    io = [
        BYOCIOBinding(
            binding_id="io:object-store-to-ray",
            kind="object-store",
            source_ref="s3://byoc-demo-bucket/datasets/demo-csv",
            sink_ref="ray://training-cluster/demo/input",
            policy_ref="policy://byoc/data-access",
        ),
        BYOCIOBinding(
            binding_id="io:local-pty-to-workspace",
            kind="websocket-pty",
            source_ref="wss://cloudshell-fog/v1/sessions/demo/pty",
            sink_ref="sourceos://local/workbench",
            policy_ref="policy://cloudshell-fog/default-profile",
        ),
        BYOCIOBinding(
            binding_id="io:beam-output-to-lake",
            kind="object-store",
            source_ref="beam://pipeline/demo/output",
            sink_ref="s3://byoc-demo-bucket/features/demo",
            policy_ref="policy://byoc/pipeline-output",
        ),
    ]
    fog = CloudShellFogBinding(
        binding_id="cloudshell-fog:demo",
        repo_ref="SocioProphet/cloudshell-fog",
        session_api_ref="POST /v1/sessions",
        websocket_pty_ref="GET /v1/sessions/{id}/pty",
        placement_mode="fog-first-cloud-fallback",
        policy_profile="default",
        runtime_connector="k8s-or-stub",
        audit_ref="cloudshell-fog:structured-audit-events",
        telemetry_ref="cloudshell-fog:opentelemetry",
    )
    return BYOCPlacementPlan(
        plan_id=_digest("byoc-placement", {"storage": len(storage), "compute": len(compute), "io": len(io)}),
        storage_profiles=storage,
        compute_targets=compute,
        io_bindings=io,
        cloudshell_fog=fog,
    )


def byoc_evidence(plan: BYOCPlacementPlan) -> dict[str, Any]:
    doc = plan.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "BYOCPlacementEvidence",
        "planId": plan.plan_id,
        "placementDigest": f"sha256:{digest}",
        "storageProfileCount": len(plan.storage_profiles),
        "computeTargetCount": len(plan.compute_targets),
        "ioBindingCount": len(plan.io_bindings),
        "evidenceReports": [
            "provider-neutral-storage",
            "provider-neutral-compute",
            "io-binding-policy",
            "fog-first-terminal-placement",
            "cloud-fallback",
            "oidc-session-auth",
            "websocket-pty-binding",
            "audit-telemetry-binding",
        ],
    }


def byoc_to_platform_record(plan: BYOCPlacementPlan) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plan.plan_id,
        "assetKind": "byoc-placement-plan",
        "name": "lattice-studio-byoc-placement-plan",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "BYOCPlacementPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://byoc/placement",
        "evidenceCorrelationId": plan.plan_id,
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "byoc",
            "kubernetes",
            "array-cluster",
            "ray",
            "beam",
            "sourceos-local",
            "cloudshell-fog",
            "object-storage",
            "websocket-pty",
            "sherlock-search",
        ],
    }
