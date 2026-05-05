from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.telemetry_runtime as telemetry_runtime  # type: ignore


def test_optional_analytics_blocks_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "analytics.citations.rendered.summary",
        {
            "local_turn_id": "turn-analytics-001",
            "citations_rendered_count": 4,
            "enhanced_citations_present": True,
            "sources_footer_present": True,
            "subject_ref": "turn://turn-analytics-001",
            "created_at": "2026-05-04T21:00:00+00:00",
        },
        control_snapshot={"product_analytics": "disabled"},
    )
    assert result["outcome"]["action"] == "BLOCK"
    assert result["receipt"]["status"] == "blocked"
    assert result["receipt"]["blocked_reason"] == "disabled_by_user"
    assert result["receipt"]["destinations"] == []


def test_reliability_records_when_analytics_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "reliability.conversation.stream.completed",
        {
            "request_id": "req-001",
            "local_turn_id": "turn-001",
            "duration_ms_bucket": 6400,
            "stream_transport": "sse_like",
            "completion_status": "clean_final_message",
            "subject_ref": "turn://turn-001",
            "created_at": "2026-05-04T21:01:00+00:00",
        },
        control_snapshot={"product_analytics": "disabled"},
    )
    assert result["outcome"]["action"] == "TRANSFORM_ALLOW"
    assert result["receipt"]["status"] == "recorded"
    assert result["receipt"]["destinations"] == ["reliability_store"]
    assert result["payload"]["fields"]["duration_ms_bucket"] == "5s_to_10s"
    assert sorted(result["receipt"]["transformed_fields"]) == ["duration_ms_bucket", "local_turn_id", "request_id"]


def test_missing_required_field_blocks_before_control_state():
    outcome = telemetry_runtime.reduce_event(
        "analytics.turn.rendered.summary",
        {
            "local_turn_id": "turn-missing-001",
            "citations_rendered_count": 1,
            "source_footer_seen": True,
            "citation_panel_opened_during_turn": False,
            "subject_ref": "turn://turn-missing-001",
            "created_at": "2026-05-04T21:02:00+00:00",
        },
        control_snapshot={"product_analytics": "enabled"},
    )
    assert outcome["action"] == "BLOCK"
    assert outcome["blocked_reason"] == "missing_required_fields:turn_has_citations"


def test_bundle_materializes_payload_event_receipt_files(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "receipts.citation_resolution.summary",
        {
            "local_turn_id": "turn-files-001",
            "citations_resolved_count": 3,
            "resolution_status": "succeeded",
            "latency_bucket": 300,
            "subject_ref": "turn://turn-files-001",
            "created_at": "2026-05-04T21:03:00+00:00",
        },
    )
    for key in ["payload_ref", "event_ref", "receipt_ref"]:
        assert Path(result["catalog_entry"][key].removeprefix("file://")).exists()
    payload = json.loads(Path(result["catalog_entry"]["payload_ref"].removeprefix("file://")).read_text(encoding="utf-8"))
    assert payload["event"] == "receipts.citation_resolution.summary"
