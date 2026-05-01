from lattice_studio.active_metadata import demo_active_metadata_spine


def test_active_metadata_spine_emits_events_from_all_product_surfaces() -> None:
    fixture = demo_active_metadata_spine()

    assert fixture["kind"] == "LatticeActiveMetadataFixture"
    assert set(fixture["sourceSurfaces"]) == {
        "product-spine",
        "model-zoo",
        "prompt-rag-eval",
        "publication-review",
    }
    events = fixture["events"]
    assert events
    assert {event["sourceSurface"] for event in events} == set(fixture["sourceSurfaces"])
    for event in events:
        assert event["kind"] == "ActiveMetadataEvent"
        assert event["assetId"]
        assert event["assetKind"]
        assert event["sourceKind"]
        assert event["sourceRepo"] == "SocioProphet/prophet-platform"
        assert event["evidenceCorrelationId"]
        assert event["promotionChannel"] == "lattice-data-governai-demo"


def test_active_metadata_spine_covers_core_asset_kinds() -> None:
    kinds = {event["assetKind"] for event in demo_active_metadata_spine()["events"]}

    assert "data-product" in kinds
    assert "publication-artifact" in kinds
    assert "model-zoo-entry" in kinds
    assert "rag-pipeline" in kinds
    assert "prompt-asset" in kinds
    assert "research-package" in kinds
    assert "reproduction-attempt" in kinds


def test_active_metadata_enrichment_records_route_to_downstream_consumers() -> None:
    fixture = demo_active_metadata_spine()
    records = fixture["enrichmentRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    assert len(records["records"]) == len(fixture["events"])
    for record in records["records"]:
        assert record["sourceKind"] == "ActiveMetadataEvent"
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["assetKind"].startswith("active-metadata-")
        assert "active-metadata" in record["compatibilitySurfaces"]
        assert "sherlock-search" in record["compatibilitySurfaces"]
        assert "slash-topics" in record["compatibilitySurfaces"]
        assert "policy-fabric" in record["compatibilitySurfaces"]


def test_active_metadata_routing_points_to_estate_consumers() -> None:
    routing = demo_active_metadata_spine()["routing"]

    assert routing["searchConsumer"] == "SocioProphet/sherlock-search#30"
    assert routing["topicConsumer"] == "SocioProphet/slash-topics#23"
    assert routing["semanticMembraneConsumer"] == "SocioProphet/new-hope#7"
    assert routing["policyConsumer"] == "SocioProphet/policy-fabric#39"
    assert routing["topologyConsumer"] == "SocioProphet/sociosphere#238"


def test_active_metadata_safety_is_fixture_only() -> None:
    safety = demo_active_metadata_spine()["safety"]

    assert safety["fixtureOnly"] is True
    assert safety["network"] == "none"
    assert safety["secrets"] == "none"
    assert safety["hostMutation"] is False
