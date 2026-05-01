from lattice_studio.demo_readiness import demo_readiness_report
from lattice_studio.runtime_profiles import BEAM_RUNTIME_REF, NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF


def test_demo_readiness_report_emits_required_shape() -> None:
    report = demo_readiness_report()

    assert report["kind"] == "LatticeDemoReadinessReport"
    assert report["metadata"]["name"] == "lattice-studio-data-governai-demo-readiness"
    assert report["readiness"]["state"] == "demo-ready"
    assert report["readiness"]["blockers"] == []
    assert report["readiness"]["network"] == "none"
    assert report["readiness"]["secrets"] == "none"
    assert report["readiness"]["hostMutation"] is False


def test_demo_readiness_report_has_required_estate_refs() -> None:
    refs = demo_readiness_report()["estateRefs"]

    assert refs["schema"] == "SourceOS-Linux/sourceos-spec#75"
    assert refs["runtimeProfiles"] == "SocioProphet/lattice-forge#11"
    assert refs["runtimePromotionManifest"] == "SocioProphet/lattice-forge#12"
    assert refs["runtimeProfileCatalog"] == "SocioProphet/prophet-platform#306"
    assert refs["mlopsRuntimeExecution"] == "SocioProphet/prophet-platform-fabric-mlops-ts-suite#34"
    assert refs["agentplaneRuntimeRefs"] == "SocioProphet/agentplane#77"
    assert refs["sherlockRuntimeIndex"] == "SocioProphet/sherlock-search#32"
    assert refs["slashRuntimeTopics"] == "SocioProphet/slash-topics#25"
    assert refs["newHopeRuntimeMembrane"] == "SocioProphet/new-hope#9"
    assert refs["policyRuntimePromotion"] == "SocioProphet/policy-fabric#42"
    assert refs["cloudshellRuntimeRoutes"] == "SocioProphet/cloudshell-fog#31"
    assert refs["topologyRuntimePromotion"] == "SocioProphet/sociosphere#243"


def test_demo_readiness_report_preserves_runtime_role_split() -> None:
    runtime_refs = demo_readiness_report()["runtimeRefs"]

    assert runtime_refs["notebookRuntimeRef"] == NOTEBOOK_RUNTIME_REF
    assert runtime_refs["rayRuntimeRef"] == RAY_RUNTIME_REF
    assert runtime_refs["beamRuntimeRef"] == BEAM_RUNTIME_REF
    assert runtime_refs["runtimeProfileBindingRef"] == "runtime-profile-binding:lattice-data-governai:0.1.0"
    assert runtime_refs["runtimePromotionManifestRef"] == "runtime-promotion-manifest:lattice-runtime-promotion-manifest:0.1.0"


def test_demo_readiness_report_checks_all_major_surfaces() -> None:
    checks = {check["name"]: check for check in demo_readiness_report()["checks"]}

    assert set(checks) == {
        "data-product",
        "runtime-profile-catalog",
        "annotation-to-training",
        "model-zoo",
        "prompt-rag-eval",
        "publication-review",
        "active-metadata",
        "trust-reputation",
        "policy-governance",
        "developer-home",
    }
    for check in checks.values():
        assert check["passed"] is True
        assert check["subjectRef"]
        assert check["evidenceRefs"]


def test_demo_readiness_report_has_demo_path_and_shell_commands() -> None:
    report = demo_readiness_report()

    assert report["demoPath"] == [
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
    ]
    commands = report["shellCommands"]
    assert "/lattice runtime pick prophet-python-ml" in commands
    assert "/lattice runtime pick prophet-ray-ml" in commands
    assert "/lattice runtime pick prophet-beam-dataops" in commands
    assert "/lattice mlops ray run community_truth_demo --runtime prophet-ray-ml --dry-run" in commands
    assert "/lattice dataops beam run community_truth_demo --runtime prophet-beam-dataops --dry-run" in commands


def test_demo_readiness_keeps_stable_runtime_promotion_blocked() -> None:
    readiness = demo_readiness_report()["readiness"]

    assert readiness["devRuntimePromotion"] == "allowed-with-generated-evidence"
    assert readiness["stableRuntimePromotion"] == "blocked-pending-external-evidence"
