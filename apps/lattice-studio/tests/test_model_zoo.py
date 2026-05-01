from lattice_studio.model_zoo import demo_model_zoo_entry
from lattice_studio.runtime_profiles import RAY_RUNTIME_REF


def test_model_zoo_fixture_emits_required_product_objects() -> None:
    fixture = demo_model_zoo_entry()

    assert fixture["kind"] == "LatticeModelZooFixture"
    assert fixture["entry"]["kind"] == "ModelZooEntry"
    assert fixture["modelCard"]["kind"] == "ModelCard"
    assert fixture["runtimeProfile"]["kind"] == "ModelRuntimeProfile"
    assert fixture["endpoint"]["kind"] == "ModelEndpoint"
    assert fixture["usePolicy"]["kind"] == "ModelUsePolicy"
    assert fixture["evaluationBundle"]["kind"] == "EvaluationBundle"
    assert fixture["factsheet"]["kind"] == "Factsheet"


def test_model_zoo_fixture_uses_ray_runtime_profile() -> None:
    fixture = demo_model_zoo_entry()
    entry = fixture["entry"]
    model_card = fixture["modelCard"]
    runtime_profile = fixture["runtimeProfile"]
    endpoint = fixture["endpoint"]
    evaluation = fixture["evaluationBundle"]
    factsheet = fixture["factsheet"]

    assert entry["modelRef"] == factsheet["subjectRef"]
    assert entry["runtimeAssetRef"] == RAY_RUNTIME_REF
    assert model_card["runtimeRef"] == RAY_RUNTIME_REF
    assert runtime_profile["runtimeAssetRef"] == RAY_RUNTIME_REF
    assert endpoint["runtimeAssetRef"] == RAY_RUNTIME_REF
    assert endpoint["servingBackend"] == "ray-serve"
    assert entry["evaluationBundleRefs"] == [evaluation["id"]]
    assert "urn:srcos:data-product:community_truth_demo" in entry["dataProductRefs"]


def test_model_zoo_fixture_emits_platform_records_for_search_and_governance() -> None:
    records = demo_model_zoo_entry()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    kinds = {record["assetKind"] for record in records["records"]}
    assert kinds == {"model-zoo-entry", "model-endpoint"}
    for record in records["records"]:
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["promotionChannel"] == "lattice-data-governai-demo"
        assert record["policyRef"]
        assert record["evidenceCorrelationId"]
    model_record = next(record for record in records["records"] if record["assetKind"] == "model-zoo-entry")
    assert "ray" in model_record["compatibilitySurfaces"]
    assert "sherlock-search" in model_record["compatibilitySurfaces"]
    assert "policy-fabric" in model_record["compatibilitySurfaces"]
    assert "agentplane" in model_record["compatibilitySurfaces"]
