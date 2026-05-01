from lattice_studio.runtime_profiles import (
    BEAM_RUNTIME_REF,
    NOTEBOOK_RUNTIME_REF,
    RAY_RUNTIME_REF,
    demo_runtime_profile_catalog,
)


def test_runtime_profile_catalog_emits_three_role_bound_profiles() -> None:
    catalog = demo_runtime_profile_catalog()

    assert catalog["kind"] == "LatticeRuntimeProfileCatalogFixture"
    assert catalog["sourceRef"] == "SocioProphet/lattice-forge#11"
    assert catalog["defaultNotebookRuntimeRef"] == NOTEBOOK_RUNTIME_REF
    assert catalog["defaultRayRuntimeRef"] == RAY_RUNTIME_REF
    assert catalog["defaultBeamRuntimeRef"] == BEAM_RUNTIME_REF
    refs = {profile["runtimeAssetRef"] for profile in catalog["profiles"]}
    assert refs == {NOTEBOOK_RUNTIME_REF, RAY_RUNTIME_REF, BEAM_RUNTIME_REF}


def test_runtime_profile_catalog_binds_roles_to_expected_runtime_assets() -> None:
    bindings = demo_runtime_profile_catalog()["roleBindings"]

    assert bindings["NotebookSession"] == NOTEBOOK_RUNTIME_REF
    assert bindings["QueryRun"] == NOTEBOOK_RUNTIME_REF
    assert bindings["ModelZooEntry"] == RAY_RUNTIME_REF
    assert bindings["ModelRuntimeProfile"] == RAY_RUNTIME_REF
    assert bindings["ModelEndpoint"] == RAY_RUNTIME_REF
    assert bindings["RayJobDryRunPlan"] == RAY_RUNTIME_REF
    assert bindings["BeamPipelineDryRunPlan"] == BEAM_RUNTIME_REF
    assert bindings["TrainingDatasetRecipe"] == BEAM_RUNTIME_REF
    assert bindings["QualityProfile"] == BEAM_RUNTIME_REF
    assert bindings["PublicationArtifact"] == NOTEBOOK_RUNTIME_REF


def test_runtime_profile_catalog_emits_platform_records() -> None:
    records = demo_runtime_profile_catalog()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    assert {record["assetId"] for record in records["records"]} == {
        NOTEBOOK_RUNTIME_REF,
        RAY_RUNTIME_REF,
        BEAM_RUNTIME_REF,
    }
    for record in records["records"]:
        assert record["assetKind"] == "runtime-profile-binding"
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["policyRef"]
        assert record["evidenceCorrelationId"]
        assert "sherlock-search" in record["compatibilitySurfaces"]
        assert "slash-topics" in record["compatibilitySurfaces"]
        assert "policy-fabric" in record["compatibilitySurfaces"]
