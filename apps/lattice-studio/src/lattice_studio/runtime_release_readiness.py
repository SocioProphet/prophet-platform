"""Runtime release readiness fixture for Lattice Studio.

This fixture records the post-evidence runtime release posture created by
Lattice Forge and Policy Fabric. It is additive to the original demo readiness
report so older demo evidence remains stable while the release lane can move
forward independently.
"""

from __future__ import annotations

from typing import Any

from .runtime_profiles import BEAM_RUNTIME_REF, NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF

RUNTIME_RELEASE_MANIFEST_REF = "runtime-promotion-manifest:lattice-runtime-promotion-manifest:0.2.0"
REQUIRED_RELEASE_REFS = {
    "runtimeEvidence": "SocioProphet/lattice-forge#13",
    "runtimePolicy": "SocioProphet/policy-fabric#43",
    "runtimeTopologyPrevious": "SocioProphet/sociosphere#243",
}


def demo_runtime_release_readiness() -> dict[str, Any]:
    profiles = [
        _profile("prophet-python-ml", NOTEBOOK_RUNTIME_REF, "notebook"),
        _profile("prophet-ray-ml", RAY_RUNTIME_REF, "ray"),
        _profile("prophet-beam-dataops", BEAM_RUNTIME_REF, "beam"),
    ]
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeRuntimeReleaseReadinessReport",
        "metadata": {
            "name": "lattice-runtime-release-readiness",
            "version": "0.1.0",
        },
        "estateRefs": REQUIRED_RELEASE_REFS,
        "manifestRef": RUNTIME_RELEASE_MANIFEST_REF,
        "profiles": profiles,
        "requiredEvidence": [
            "RuntimeAsset",
            "SBOM",
            "scan-report",
            "attestation",
            "signature",
            "external-scanner-evidence",
            "external-signing-authority-evidence",
            "human-approval",
        ],
        "decisionPosture": {
            "devRelease": "allow",
            "stableRelease": "allow-with-required-evidence",
            "generatedOnlyStableRelease": "deny",
            "policyFabricRequired": True,
        },
        "safety": {"network": "none", "secrets": "none", "hostMutation": False},
    }


def _profile(name: str, runtime_ref: str, runtime_class: str) -> dict[str, Any]:
    return {
        "name": name,
        "runtimeRef": runtime_ref,
        "runtimeClass": runtime_class,
        "manifestRef": RUNTIME_RELEASE_MANIFEST_REF,
        "externalScannerEvidenceRef": f"urn:srcos:evidence:{name}:external-scanner",
        "externalSigningEvidenceRef": f"urn:srcos:evidence:{name}:external-signing-authority",
        "humanApprovalEvidenceRef": f"urn:srcos:evidence:{name}:human-approval",
        "releaseDecision": "allow-with-required-evidence",
    }
