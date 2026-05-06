from __future__ import annotations

import pytest

from cell_service.social_environment import (
    SocialEnvironmentError,
    anti_manipulation_assessment,
    reputation_delta_event,
    reputation_delta_fact,
    social_environment_snapshot,
    social_snapshot_fact,
    source_quality_fact,
)


def sample_signals() -> list[dict]:
    return [
        {
            "id": "signal://1",
            "cell_id": "cell://demo",
            "source_id": "source://alpha",
            "watch_id": "watch://runtime",
            "observed_at": "2026-05-04T00:00:00Z",
            "relevance_score": 0.9,
            "confidence_score": 0.8,
            "evidence_refs": ["evidence://same"],
        },
        {
            "id": "signal://2",
            "cell_id": "cell://demo",
            "source_id": "source://alpha",
            "watch_id": "watch://runtime",
            "observed_at": "2026-05-04T00:01:00Z",
            "relevance_score": 0.7,
            "confidence_score": 0.6,
            "evidence_refs": ["evidence://same"],
        },
        {
            "id": "signal://3",
            "cell_id": "cell://demo",
            "source_id": "source://beta",
            "watch_id": "watch://runtime",
            "observed_at": "2026-05-04T00:02:00Z",
            "relevance_score": 0.2,
            "confidence_score": 0.4,
            "evidence_refs": ["evidence://same"],
        },
    ]


def sample_feedback() -> list[dict]:
    return [
        {"id": "fb://1", "cell_id": "cell://demo", "signal_id": "signal://1", "actor_ref": "human://a", "action": "mark_relevant", "created_at": "2026-05-04T00:10:00Z"},
        {"id": "fb://2", "cell_id": "cell://demo", "signal_id": "signal://2", "actor_ref": "human://a", "action": "dismiss", "created_at": "2026-05-04T00:11:00Z"},
        {"id": "fb://3", "cell_id": "cell://demo", "signal_id": "signal://2", "actor_ref": "human://b", "action": "mute_source", "created_at": "2026-05-04T00:12:00Z"},
        {"id": "fb://4", "cell_id": "cell://demo", "signal_id": "signal://3", "actor_ref": "human://c", "action": "mark_irrelevant", "created_at": "2026-05-04T00:13:00Z"},
    ]


def sample_interactions() -> list[dict]:
    return [
        {"peer_ref": "human://a", "actor_ref": "human://a", "claim_ref": "claim://same", "observed_at": "2026-05-04T00:00:00Z", "authority_score": 0.7, "popularity_score": 0.8, "expertise_score": 0.9},
        {"peer_ref": "human://a", "actor_ref": "human://a", "claim_ref": "claim://same", "observed_at": "2026-05-04T00:01:00Z", "authority_score": 0.7, "popularity_score": 0.8, "expertise_score": 0.9},
        {"peer_ref": "human://a", "actor_ref": "human://a", "claim_ref": "claim://same", "observed_at": "2026-05-04T00:02:00Z", "authority_score": 0.7, "popularity_score": 0.8, "expertise_score": 0.9},
        {"peer_ref": "human://stale", "actor_ref": "human://stale", "claim_ref": "claim://old", "observed_at": "2026-03-01T00:00:00Z"},
    ]


def test_social_environment_snapshot_detects_hygiene_and_amplification() -> None:
    peers = [
        {"id": "peer://a", "peer_ref": "human://a", "community_ref": "community://runtime"},
        {"id": "peer://b", "peer_ref": "human://b", "community_ref": "community://runtime"},
        {"id": "peer://stale", "peer_ref": "human://stale", "community_ref": "community://old"},
    ]

    snapshot = social_environment_snapshot(
        cell_id="cell://demo",
        peers=peers,
        interactions=sample_interactions(),
        signals=sample_signals(),
        feedback_events=sample_feedback(),
        now="2026-05-06T00:00:00Z",
    )

    assert snapshot["peer_count"] == 3
    assert snapshot["stale_tie_count"] == 1
    assert snapshot["emerging_community_count"] == 1
    assert snapshot["attention_sink_count"] == 1
    assert snapshot["relationship_hygiene"]
    assert any(flag.startswith("claim:claim://same") for flag in snapshot["coordinated_amplification_flags"])

    fact = social_snapshot_fact(snapshot)
    assert fact["cell_id"] == "cell://demo"
    assert fact["peer_count"] == 3
    assert fact["body"]["stale_ties"] == ["human://stale"]


def test_reputation_delta_event_includes_anti_manipulation_and_components() -> None:
    event = reputation_delta_event(
        cell_id="cell://demo",
        subject_ref="source://alpha",
        subject_kind="source",
        context="runtime-watch",
        evidence_refs=["evidence://1", "evidence://2"],
        feedback_events=sample_feedback(),
        interactions=sample_interactions(),
    )

    assert event["subject_ref"] == "source://alpha"
    assert event["anti_manipulation"]["flags"]
    assert event["policy_effect"] == "review_required"
    assert event["confidence_interval"]["low"] <= event["delta"] <= event["confidence_interval"]["high"]
    assert set(event["score_components"]) == {"trust", "authority", "popularity", "expertise"}

    fact = reputation_delta_fact(event)
    assert fact["subject_kind"] == "source"
    assert fact["anti_manipulation_flags"] == event["anti_manipulation"]["flags"]


def test_anti_manipulation_assessment_flags_repetition() -> None:
    anti = anti_manipulation_assessment(
        subject_ref="source://alpha",
        evidence_refs=["evidence://1"],
        interactions=sample_interactions(),
    )

    assert anti["sybil_score"] > 0
    assert "coordinated_claim_amplification" in anti["flags"]


def test_source_quality_fact_aggregates_feedback_and_scores() -> None:
    fact = source_quality_fact(
        cell_id="cell://demo",
        source_id="source://alpha",
        source_kind="repo",
        event_at="2026-05-06T00:00:00Z",
        feedback_events=sample_feedback(),
        signals=sample_signals(),
    )

    assert fact["source_id"] == "source://alpha"
    assert fact["relevance_mean"] == 0.8
    assert fact["confidence_mean"] == 0.7
    assert fact["accepted_count"] == 1
    assert fact["muted_count"] == 1


def test_reputation_requires_evidence() -> None:
    with pytest.raises(SocialEnvironmentError, match="evidence_refs"):
        reputation_delta_event(
            cell_id="cell://demo",
            subject_ref="source://alpha",
            subject_kind="source",
            context="runtime-watch",
            evidence_refs=[],
            feedback_events=[],
            interactions=[],
        )
