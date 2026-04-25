from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.telemetry_runtime as telemetry_runtime  # type: ignore


def test_reduce_event_is_deterministic_for_same_input():
    payload = {
        "request_id": "req-replay-001",
        "local_turn_id": "turn-replay-001",
        "duration_ms_bucket": 6400,
        "stream_transport": "sse_like",
        "completion_status": "clean_final_message",
        "subject_ref": "turn://turn-replay-001",
        "created_at": "2026-04-25T14:20:00+00:00",
    }
    control_snapshot = {"product_analytics": "disabled"}

    first = telemetry_runtime.reduce_event(
        "reliability.conversation.stream.completed",
        payload,
        control_snapshot=control_snapshot,
        policy_version="telemetry-policy-v0.1",
    )
    second = telemetry_runtime.reduce_event(
        "reliability.conversation.stream.completed",
        payload,
        control_snapshot=control_snapshot,
        policy_version="telemetry-policy-v0.1",
    )

    assert first == second
    assert first["action"] == "TRANSFORM_ALLOW"
    assert first["reduced_fields"]["duration_ms_bucket"] == "5s_to_10s"


def test_missing_required_fields_blocks_before_optional_controls_apply():
    payload = {
        "local_turn_id": "turn-missing-001",
        "citations_rendered_count": 2,
        "source_footer_seen": True,
        "citation_panel_opened_during_turn": False,
        "subject_ref": "turn://turn-missing-001",
        "created_at": "2026-04-25T14:21:00+00:00",
    }
    outcome = telemetry_runtime.reduce_event(
        "analytics.turn.rendered.summary",
        payload,
        control_snapshot={"product_analytics": "enabled"},
    )
    assert outcome["action"] == "BLOCK"
    assert outcome["blocked_reason"] == "missing_required_fields:turn_has_citations"


def test_high_privacy_blocks_optional_analytics_in_reduce_event():
    payload = {
        "local_turn_id": "turn-high-privacy-001",
        "citations_rendered_count": 4,
        "enhanced_citations_present": True,
        "sources_footer_present": True,
        "subject_ref": "turn://turn-high-privacy-001",
        "created_at": "2026-04-25T14:22:00+00:00",
    }
    outcome = telemetry_runtime.reduce_event(
        "analytics.citations.rendered.summary",
        payload,
        control_snapshot={"product_analytics": "high_privacy"},
    )
    assert outcome["action"] == "BLOCK"
    assert outcome["blocked_reason"] == "disabled_by_user"
    assert outcome["destinations"] == []
