from lattice_studio.product_spine import demo_product_spine


def test_product_spine_emits_approved_vertical_story() -> None:
    spine = demo_product_spine()

    assert spine["kind"] == "LatticeDataGovernAIVerticalDemo"
    assert spine["spine"] == [
        "CatalogAsset",
        "DataProduct",
        "AnnotationSet",
        "RuntimeAsset",
        "NotebookSession",
        "QueryRun",
        "PromotionCandidate",
        "EvaluationBundle",
        "Factsheet",
        "PublicationArtifact",
        "PlatformAssetRecord",
    ]
    assert spine["dataProduct"]["kind"] == "DataProduct"
    assert spine["annotationSet"]["kind"] == "AnnotationSet"
    assert spine["queryRun"]["kind"] == "QueryRun"
    assert spine["promotionCandidate"]["kind"] == "PromotionCandidate"
    assert spine["evaluationBundle"]["kind"] == "EvaluationBundle"
    assert spine["factsheet"]["kind"] == "Factsheet"
    assert spine["publicationArtifact"]["kind"] == "PublicationArtifact"


def test_product_spine_preserves_data_runtime_notebook_evidence_links() -> None:
    spine = demo_product_spine()

    data_product = spine["dataProduct"]
    annotation_set = spine["annotationSet"]
    session = spine["notebookSession"]
    query_run = spine["queryRun"]
    promotion = spine["promotionCandidate"]
    evaluation = spine["evaluationBundle"]
    factsheet = spine["factsheet"]
    publication = spine["publicationArtifact"]

    assert data_product["catalogAssetRef"] == spine["catalogAsset"]["catalogAssetId"]
    assert annotation_set["subjectRefs"] == [data_product["id"]]
    assert query_run["dataProductRef"] == data_product["id"]
    assert query_run["notebookSessionRef"] == session["sessionId"]
    assert promotion["sourceRefs"] == [query_run["queryRunId"], annotation_set["id"]]
    assert evaluation["subjectRef"] == promotion["targetRef"]
    assert factsheet["evaluationRefs"] == [evaluation["id"]]
    assert publication["artifactRefs"]["dataProductRefs"] == [data_product["id"]]
    assert publication["artifactRefs"]["runtimeRefs"] == [session["runtimeAssetId"]]
    assert publication["artifactRefs"]["notebookRefs"] == [session["sessionId"]]


def test_product_spine_emits_platform_asset_records_for_governed_surfaces() -> None:
    records = demo_product_spine()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    kinds = {record["assetKind"] for record in records["records"]}
    assert {
        "data-product",
        "annotation-set",
        "query-run",
        "promotion-candidate",
        "evaluation-bundle",
        "factsheet",
        "publication-artifact",
    } == kinds
    for record in records["records"]:
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["promotionChannel"] == "lattice-data-governai-demo"
        assert "lattice-studio" in record["compatibilitySurfaces"] or "governai" in record["compatibilitySurfaces"]
