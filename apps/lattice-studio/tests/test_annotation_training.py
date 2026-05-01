from lattice_studio.annotation_training import demo_annotation_training_loop
from lattice_studio.runtime_profiles import BEAM_RUNTIME_REF, RAY_RUNTIME_REF


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
    assert training["runtimeRef"] == BEAM_RUNTIME_REF
    assert training["trainingRuntimeRef"] == RAY_RUNTIME_REF
    assert evaluation["sourceDataProductRefs"] == [data_product_ref]
    assert evaluation["annotationSetRefs"] == [annotation_ref]
    assert evaluation["split"] == "eval"
    assert evaluation["evaluationAllowed"] is True
    assert evaluation["runtimeRef"] == BEAM_RUNTIME_REF
    assert evaluation["evaluationRuntimeRef"] == RAY_RUNTIME_REF
    assert recipe["runtimeRef"] == BEAM_RUNTIME_REF
    assert recipe["trainingRuntimeRef"] == RAY_RUNTIME_REF
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
    training_record = next(record for record in records["records"] if record["assetKind"] == "training-dataset")
    assert "ray" in training_record["compatibilitySurfaces"]
    assert "beam" in training_record["compatibilitySurfaces"]
    eval_record = next(record for record in records["records"] if record["assetKind"] == "evaluation-dataset")
    assert "ray" in eval_record["compatibilitySurfaces"]
    assert "beam" in eval_record["compatibilitySurfaces"]
    recipe_record = next(record for record in records["records"] if record["assetKind"] == "training-dataset-recipe")
    assert "beam" in recipe_record["compatibilitySurfaces"]
