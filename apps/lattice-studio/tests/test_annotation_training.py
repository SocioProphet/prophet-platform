from lattice_studio.annotation_training import demo_annotation_training_loop


def test_annotation_training_loop_emits_required_objects() -> None:
    fixture = demo_annotation_training_loop()

    assert fixture["kind"] == "LatticeAnnotationTrainingLoopFixture"
    assert fixture["dataProduct"]["kind"] == "DataProduct"
    assert fixture["annotationSet"]["kind"] == "AnnotationSet"
    assert fixture["labelingProject"]["kind"] == "LabelingProject"
    assert fixture["annotationReliabilityScore"]["kind"] == "AnnotationReliabilityScore"
    assert fixture["trainingDataset"]["kind"] == "TrainingDataset"
    assert fixture["evaluationDataset"]["kind"] == "EvaluationDataset"
    assert fixture["trainingDatasetRecipe"]["kind"] == "TrainingDatasetRecipe"
    assert fixture["trainingUsePolicy"]["kind"] == "TrainingUsePolicy"


def test_annotation_training_loop_preserves_label_lineage_and_splits() -> None:
    fixture = demo_annotation_training_loop()
    data_product_ref = "urn:srcos:data-product:community_truth_demo"
    annotation_ref = "urn:srcos:annotation-set:community_truth_demo_labels"
    project = fixture["labelingProject"]
    reliability = fixture["annotationReliabilityScore"]
    training = fixture["trainingDataset"]
    evaluation = fixture["evaluationDataset"]
    recipe = fixture["trainingDatasetRecipe"]

    assert project["dataProductRef"] == data_product_ref
    assert project["annotationSetRefs"] == [annotation_ref]
    assert reliability["annotationSetRef"] == annotation_ref
    assert reliability["labelingProjectRef"] == project["id"]
    assert training["sourceDataProductRefs"] == [data_product_ref]
    assert training["annotationSetRefs"] == [annotation_ref]
    assert training["split"] == "train"
    assert training["trainingAllowed"] is True
    assert evaluation["sourceDataProductRefs"] == [data_product_ref]
    assert evaluation["annotationSetRefs"] == [annotation_ref]
    assert evaluation["split"] == "eval"
    assert evaluation["evaluationAllowed"] is True
    assert training["reliabilityScoreRef"] == reliability["id"]
    assert evaluation["reliabilityScoreRef"] == reliability["id"]
    assert recipe["outputs"] == [training["id"], evaluation["id"]]


def test_annotation_training_loop_enforces_use_policy_and_reliability() -> None:
    fixture = demo_annotation_training_loop()
    reliability = fixture["annotationReliabilityScore"]
    use_policy = fixture["trainingUsePolicy"]
    training = fixture["trainingDataset"]
    evaluation = fixture["evaluationDataset"]

    assert reliability["score"] == 0.81
    assert reliability["components"]["reviewerReputation"] >= 0.8
    assert reliability["components"]["sourceTrust"] >= 0.8
    assert use_policy["subjectRefs"] == [training["id"], evaluation["id"]]
    assert "demo-training" in use_policy["allowedUses"]
    assert "evaluation" in use_policy["allowedUses"]
    assert "external-sale" in use_policy["forbiddenUses"]
    assert "production-decisioning" in use_policy["forbiddenUses"]
    assert use_policy["attributionRequired"] is True


def test_annotation_training_loop_emits_platform_records() -> None:
    records = demo_annotation_training_loop()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    kinds = {record["assetKind"] for record in records["records"]}
    assert kinds == {
        "labeling-project",
        "annotation-reliability-score",
        "training-dataset",
        "evaluation-dataset",
        "training-dataset-recipe",
    }
    for record in records["records"]:
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["promotionChannel"] == "lattice-data-governai-demo"
        assert record["policyRef"]
        assert record["evidenceCorrelationId"]
    training_record = next(record for record in records["records"] if record["assetKind"] == "training-dataset")
    assert "ray" in training_record["compatibilitySurfaces"]
    assert "model-zoo" in training_record["compatibilitySurfaces"]
    eval_record = next(record for record in records["records"] if record["assetKind"] == "evaluation-dataset")
    assert "governai" in eval_record["compatibilitySurfaces"]
    assert "evaluation-lab" in eval_record["compatibilitySurfaces"]
