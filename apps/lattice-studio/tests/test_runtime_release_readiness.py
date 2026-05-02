from lattice_studio.runtime_profiles import BEAM_RUNTIME_REF, NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF
from lattice_studio.runtime_release_readiness import (
    RUNTIME_RELEASE_MANIFEST_REF,
    demo_runtime_release_readiness,
)


def test_runtime_release_readiness_shape_and_refs() -> None:
    report = demo_runtime_release_readiness()

    assert report["kind"] == "LatticeRuntimeReleaseReadinessReport"
    assert report["metadata"]["name"] == "lattice-runtime-release-readiness"
    assert report["manifestRef"] == RUNTIME_RELEASE_MANIFEST_REF
    assert report["estateRefs"]["runtimeEvidence"] == "SocioProphet/lattice-forge#13"
    assert report["estateRefs"]["runtimePolicy"] == "SocioProphet/policy-fabric#43"


def test_runtime_release_readiness_covers_all_runtime_profiles() -> None:
    report = demo_runtime_release_readiness()
    profiles = {profile["runtimeRef"]: profile for profile in report["profiles"]}

    assert set(profiles) == {NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF, BEAM_RUNTIME_REF}
    assert profiles[NOTEBOOK_RUNTIME_REF]["runtimeClass"] == "notebook"
    assert profiles[RAY_RUNTIME_REF]["runtimeClass"] == "ray"
    assert profiles[BEAM_RUNTIME_REF]["runtimeClass"] == "beam"
    for profile in profiles.values():
        assert profile["manifestRef"] == RUNTIME_RELEASE_MANIFEST_REF
        assert profile["externalScannerEvidenceRef"].startswith("urn:srcos:evidence:")
        assert profile["externalSigningEvidenceRef"].startswith("urn:srcos:evidence:")
        assert profile["humanApprovalEvidenceRef"].startswith("urn:srcos:evidence:")
        assert profile["releaseDecision"] == "allow-with-required-evidence"


def test_runtime_release_readiness_requires_generated_and_external_evidence() -> None:
    required = set(demo_runtime_release_readiness()["requiredEvidence"])

    assert {
        "RuntimeAsset",
        "SBOM",
        "scan-report",
        "attestation",
        "signature",
        "external-scanner-evidence",
        "external-signing-authority-evidence",
        "human-approval",
    } <= required


def test_runtime_release_readiness_decision_posture_and_safety() -> None:
    report = demo_runtime_release_readiness()
    posture = report["decisionPosture"]
    safety = report["safety"]

    assert posture["devRelease"] == "allow"
    assert posture["stableRelease"] == "allow-with-required-evidence"
    assert posture["generatedOnlyStableRelease"] == "deny"
    assert posture["policyFabricRequired"] is True
    assert safety == {"network": "none", "secrets": "none", "hostMutation": False}
