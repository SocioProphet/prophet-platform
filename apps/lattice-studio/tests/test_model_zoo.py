from lattice_studio.model_zoo import demo_model_zoo_entry


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


def test_model_zoo_fixture_preserves_lineage_runtime_policy_and_eval_refs() -> None:
    fixture = demo_model_zoo_entry()
    entry = fixture["entry"]
    model_card = fixture["modelCard"]
    runtime_profile = fixture["runtimeProfile"]
    endpoint = fixture["endpoint"]
    use_policy = fixture["usePolicy"]
    evaluation = fixture["evaluationBundle"]
    factsheet = fixture["factsheet"]

    assert entry["modelRef"] == factsheet["subjectRef"]
    assert entry["modelCardRef"] == model_card["id"]
    assert entry["runtimeProfileRef"] == runtime_profile["id"]
    assert entry["endpointRef"] == endpoint["id"]
    assert entry["usePolicyRef"] == use_policy["id"]
    assert entry["factsheetRef"] == factsheet["id"]
    assert entry["evaluationBundleRefs"] == [evaluation["id"]]
    assert "urn:srcos:data-product:community_truth_demo" in entry["dataProductRefs"]
    assert runtime_profile["runtimeAssetRef"] == "runtime-asset:prophet-python-ml:0.1.0"
    assert endpoint["servingBackend"] == "ray-serve"
    assert endpoint["state"] == "candidate-dry-run"
    assert "production-decisioning" in use_policy["forbiddenUses"]
    assert "promotion" in use_policy["requiresApprovalFor"]


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
    assert "sherlock-search" in model_record["compatibilitySurfaces"]
    assert "policy-fabric" in model_record["compatibilitySurfaces"]
    assert "agentplane" in model_record["compatibilitySurfaces"]
