from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.telemetry_runtime as telemetry_runtime  # type: ignore


def test_reduce_event_blocks_optional_analytics_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    payload = {
        "local_turn_id": "turn-123",
        "citations_rendered_count": 4,
        "enhanced_citations_present": True,
        "sources_footer_present": True,
        "subject_ref": "turn://turn-123",
        "created_at": "2026-04-25T13:30:00+00:00",
    }
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "analytics.citations.rendered.summary",
        payload,
        control_snapshot={"product_analytics": "disabled"},
    )
    assert result["outcome"]["action"] == "BLOCK"
    assert result["receipt"]["status"] == "blocked"
    assert result["receipt"]["blocked_reason"] == "disabled_by_user"
    assert result["catalog_entry"]["service"] == "telemetry-runtime"


def test_reduce_event_allows_reliability_when_analytics_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    payload = {
        "request_id": "req-123",
        "local_turn_id": "turn-123",
        "duration_ms_bucket": 6400,
        "stream_transport": "sse_like",
        "completion_status": "clean_final_message",
        "subject_ref": "turn://turn-123",
        "created_at": "2026-04-25T13:31:00+00:00",
    }
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "reliability.conversation.stream.completed",
        payload,
        control_snapshot={"product_analytics": "disabled"},
    )
    assert result["outcome"]["action"] == "TRANSFORM_ALLOW"
    assert "request_id" in result["outcome"]["transformed_fields"]
    assert "local_turn_id" in result["outcome"]["transformed_fields"]
    assert result["payload"]["fields"]["duration_ms_bucket"] == "5s_to_10s"
    assert result["receipt"]["status"] == "recorded"


def test_manifest_loader_raises_for_unknown_event():
    try:
        telemetry_runtime.load_manifest("does.not.exist")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for unknown manifest")
