from lattice_studio.publication_review import demo_publication_review_package


def test_publication_review_fixture_emits_required_objects() -> None:
    fixture = demo_publication_review_package()

    assert fixture["kind"] == "LatticePublicationReviewFixture"
    assert fixture["publicationArtifact"]["kind"] == "PublicationArtifact"
    assert fixture["researchPackage"]["kind"] == "ResearchPackage"
    assert fixture["reviewThread"]["kind"] == "ReviewThread"
    assert fixture["reviewDecision"]["kind"] == "ReviewDecision"
    assert fixture["citationGraph"]["kind"] == "CitationGraph"
    assert fixture["reproductionAttempt"]["kind"] == "ReproductionAttempt"


def test_publication_review_fixture_preserves_reproduction_inputs_outputs() -> None:
    fixture = demo_publication_review_package()
    publication = fixture["publicationArtifact"]
    package = fixture["researchPackage"]
    attempt = fixture["reproductionAttempt"]

    assert package["publicationArtifactRef"] == publication["id"]
    assert package["dataProductRefs"] == ["urn:srcos:data-product:community_truth_demo"]
    assert package["runtimeRefs"] == ["runtime-asset:prophet-python-ml:0.1.0"]
    assert package["reproductionRecipeRef"] == publication["reproduction"]["recipeRef"]
    assert package["reproducibilityScore"] == publication["reproduction"]["score"]
    assert attempt["researchPackageRef"] == package["id"]
    assert attempt["recipeRef"] == package["reproductionRecipeRef"]
    assert attempt["runtimeRef"] == "runtime-asset:prophet-python-ml:0.1.0"
    assert publication["id"] in attempt["outputRefs"]
    assert attempt["status"] == "partial-pass"
    assert attempt["verified"] is False


def test_publication_review_fixture_links_review_and_citations() -> None:
    fixture = demo_publication_review_package()
    publication = fixture["publicationArtifact"]
    package = fixture["researchPackage"]
    review = fixture["reviewThread"]
    decision = fixture["reviewDecision"]
    citation_graph = fixture["citationGraph"]

    assert review["publicationArtifactRef"] == publication["id"]
    assert review["researchPackageRef"] == package["id"]
    assert review["state"] == "under-review"
    assert decision["reviewThreadRef"] == review["id"]
    assert decision["state"] == "needs-revision"
    assert citation_graph["publicationArtifactRef"] == publication["id"]
    edge_rels = {edge["rel"] for edge in citation_graph["edges"]}
    assert {"uses-data", "supported-by-evaluation", "describes-model"} <= edge_rels


def test_publication_review_fixture_emits_platform_records() -> None:
    records = demo_publication_review_package()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    kinds = {record["assetKind"] for record in records["records"]}
    assert kinds == {"research-package", "review-thread", "citation-graph", "reproduction-attempt"}
    for record in records["records"]:
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["promotionChannel"] == "lattice-data-governai-demo"
        assert record["policyRef"]
        assert record["evidenceCorrelationId"]
    package_record = next(record for record in records["records"] if record["assetKind"] == "research-package")
    assert "sherlock-search" in package_record["compatibilitySurfaces"]
    assert "slash-topics" in package_record["compatibilitySurfaces"]
    attempt_record = next(record for record in records["records"] if record["assetKind"] == "reproduction-attempt")
    assert "agentplane" in attempt_record["compatibilitySurfaces"]
