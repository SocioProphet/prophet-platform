"""SourceOS M2 + TopoLVM placement for local VM and Kubernetes pools.

This bridge treats M2 proof bundles as governed local filesystem registry inputs
and maps them onto TopoLVM-backed local storage for Inception agent clusters,
local VMs, and Kubernetes pool joins. It remains side-effect-free: no disk
mutation, no kexec, no remote state mutation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

PlacementMode = Literal["local-vm", "k8s-pool-join", "inception-agent-cluster"]


@dataclass(frozen=True)
class TopoLVMVolumeClaim:
    claim_id: str
    storage_class: str
    size: str
    mount_path: str
    access_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claimId": self.claim_id,
            "storageClass": self.storage_class,
            "size": self.size,
            "mountPath": self.mount_path,
            "accessMode": self.access_mode,
        }


@dataclass(frozen=True)
class M2RegistryMount:
    registry_root: str
    proof_index_ref: str
    release_pointer_ref: str
    mounted_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registryRoot": self.registry_root,
            "proofIndexRef": self.proof_index_ref,
            "releasePointerRef": self.release_pointer_ref,
            "mountedArtifacts": self.mounted_artifacts,
        }


@dataclass(frozen=True)
class M2TopoLVMPlacementPlan:
    plan_id: str
    mode: PlacementMode
    cluster_ref: str
    node_pool_ref: str
    topolvm_claims: list[TopoLVMVolumeClaim]
    m2_registry_mount: M2RegistryMount
    inception_refs: list[str]
    safety_boundary: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "M2TopoLVMPlacementPlan",
            "planId": self.plan_id,
            "mode": self.mode,
            "clusterRef": self.cluster_ref,
            "nodePoolRef": self.node_pool_ref,
            "topolvmClaims": [claim.to_dict() for claim in self.topolvm_claims],
            "m2RegistryMount": self.m2_registry_mount.to_dict(),
            "inceptionRefs": self.inception_refs,
            "safetyBoundary": self.safety_boundary,
            "createdAt": self.created_at,
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_m2_topolvm_placement_plan() -> M2TopoLVMPlacementPlan:
    claims = [
        TopoLVMVolumeClaim(
            claim_id="topolvm-claim:m2-registry",
            storage_class="topolvm-provisioner",
            size="20Gi",
            mount_path="/var/lib/sourceos/m2-registry",
            access_mode="ReadWriteOnce",
        ),
        TopoLVMVolumeClaim(
            claim_id="topolvm-claim:agent-workspace",
            storage_class="topolvm-provisioner",
            size="50Gi",
            mount_path="/workspace",
            access_mode="ReadWriteOnce",
        ),
    ]
    mount = M2RegistryMount(
        registry_root="file:///var/lib/sourceos/m2-registry",
        proof_index_ref="contracts/sourceos/examples/proof-index.m2-demo.v0.json",
        release_pointer_ref="sourceos/demo/0.1.0/release-pointer.json",
        mounted_artifacts=[
            "config-source.json",
            "release-set.json",
            "boot-release-set.json",
            "nlboot-crosswalk.json",
            "fingerprint.json",
            "compliance-result.json",
            "proof-index.json",
        ],
    )
    payload = {"mode": "inception-agent-cluster", "cluster": "k8s://local-inception/demo"}
    return M2TopoLVMPlacementPlan(
        plan_id=_digest("m2-topolvm-placement", payload),
        mode="inception-agent-cluster",
        cluster_ref="k8s://local-inception/demo",
        node_pool_ref="k8s-nodepool://local-vm/topolvm-agents",
        topolvm_claims=claims,
        m2_registry_mount=mount,
        inception_refs=[
            "ontogenesis:Platform/Inception.ttl#MinIO",
            "ontogenesis:Platform/Inception.ttl#Bus",
            "ontogenesis:Platform/Inception.ttl#ROCKZDB",
            "ontogenesis:Platform/Inception.ttl#GIB",
            "ontogenesis:Platform/Inception.ttl#SAPIEN",
        ],
        safety_boundary=[
            "no-host-mutation",
            "no-kexec",
            "no-remote-state-mutation",
            "filesystem-registry-proof-only",
            "topolvm-mount-dry-run",
        ],
    )


def m2_topolvm_evidence(plan: M2TopoLVMPlacementPlan) -> dict[str, Any]:
    doc = plan.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "M2TopoLVMEvidence",
        "planId": plan.plan_id,
        "placementDigest": f"sha256:{digest}",
        "claimCount": len(plan.topolvm_claims),
        "mountedArtifactCount": len(plan.m2_registry_mount.mounted_artifacts),
        "evidenceReports": [
            "sourceos-m2-filesystem-registry",
            "topolvm-volume-claims",
            "local-vm-k8s-pool-join",
            "inception-agent-cluster-binding",
            "proof-index-mounted",
            "safety-boundary-no-host-mutation",
        ],
    }


def m2_topolvm_to_platform_record(plan: M2TopoLVMPlacementPlan) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plan.plan_id,
        "assetKind": "m2-topolvm-placement-plan",
        "name": "sourceos-m2-topolvm-inception-placement",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "M2TopoLVMPlacementPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://sourceos/m2-topolvm-placement",
        "evidenceCorrelationId": plan.plan_id,
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "sourceos-m2",
            "topolvm",
            "kubernetes",
            "local-vm",
            "inception-agent-cluster",
            "byoc",
            "cloudshell-fog",
            "lattice-studio",
            "sherlock-search",
        ],
    }
