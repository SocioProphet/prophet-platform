from lattice_studio.trust_reputation import demo_trust_reputation_signals


def test_trust_reputation_fixture_emits_required_signals() -> None:
    fixture = demo_trust_reputation_signals()

    assert fixture["kind"] == "LatticeTrustReputationFixture"
    assert fixture["signals"]
    signal_kinds = {signal["signalKind"] for signal in fixture["signals"]}
    assert "DatasetTrustScore" in signal_kinds
    assert "AnnotationReliability" in signal_kinds
    assert "EvaluationConfidence" in signal_kinds
    assert "ReproducibilityScore" in signal_kinds


def test_trust_reputation_signals_have_scores_components_and_evidence() -> None:
    fixture = demo_trust_reputation_signals()

    for signal in fixture["signals"]:
        assert signal["kind"] == "TrustSignal"
        assert 0 <= signal["score"] <= 1
        assert signal["subjectRef"]
        assert signal["components"]
        assert signal["evidenceRefs"]
        assert signal["policyRef"] == "urn:srcos:policy:lattice-trust-reputation-demo"


def test_trust_posture_summary_aggregates_subjects_and_evidence() -> None:
    fixture = demo_trust_reputation_signals()
    posture = fixture["trustPosture"]

    assert posture["kind"] == "TrustPostureSummary"
    assert posture["promotionRisk"] == "medium"
    assert 0 <= posture["overallScore"] <= 1
    assert posture["subjectRefs"] == [signal["subjectRef"] for signal in fixture["signals"]]
    all_evidence = {evidence for signal in fixture["signals"] for evidence in signal["evidenceRefs"]}
    assert set(posture["evidenceRefs"]) == all_evidence
    assert posture["policyRef"] == "urn:srcos:policy:lattice-trust-reputation-demo"


def test_trust_reputation_platform_records_route_to_governance_consumers() -> None:
    records = demo_trust_reputation_signals()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    kinds = {record["assetKind"] for record in records["records"]}
    assert "trust-signal" in kinds
    assert "trust-posture-summary" in kinds
    for record in records["records"]:
        assert record["producerRepo"] == "SocioProphet/prophet-platform"
        assert record["promotionChannel"] == "lattice-data-governai-demo"
        assert record["policyRef"] == "urn:srcos:policy:lattice-trust-reputation-demo"
        assert record["evidenceCorrelationId"]
    summary = next(record for record in records["records"] if record["assetKind"] == "trust-posture-summary")
    assert "policy-fabric" in summary["compatibilitySurfaces"]
    assert "slash-topics" in summary["compatibilitySurfaces"]
    assert "new-hope" in summary["compatibilitySurfaces"]


def test_trust_reputation_safety_is_fixture_only() -> None:
    safety = demo_trust_reputation_signals()["safety"]

    assert safety["fixtureOnly"] is True
    assert safety["network"] == "none"
    assert safety["secrets"] == "none"
    assert safety["hostMutation"] is False
