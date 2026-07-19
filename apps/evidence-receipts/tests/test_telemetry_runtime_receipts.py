from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.telemetry_runtime as telemetry_runtime  # type: ignore


def test_high_privacy_blocks_optional_analytics(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "analytics.turn.rendered.summary",
        {
            "local_turn_id": "turn-privacy-001",
            "turn_has_citations": True,
            "citations_rendered_count": 2,
            "source_footer_seen": True,
            "citation_panel_opened_during_turn": False,
            "subject_ref": "turn://turn-privacy-001",
        },
        control_snapshot={"product_analytics": "high_privacy"},
    )
    assert result["outcome"]["action"] == "BLOCK"
    assert result["receipt"]["status"] == "blocked"
    assert result["receipt"]["blocked_reason"] == "disabled_by_user"


def test_receipt_contains_transformed_field_names_and_destinations(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    result = telemetry_runtime.emit_event_bundle(
        "telemetry-runtime",
        "reliability.conversation.stream.completed",
        {
            "request_id": "req-x",
            "local_turn_id": "turn-x",
            "duration_ms_bucket": 1200,
            "stream_transport": "sse_like",
            "completion_status": "clean_final_message",
            "subject_ref": "turn://turn-x",
        },
    )
    receipt = result["receipt"]
    assert receipt["status"] == "recorded"
    assert receipt["destinations"] == ["reliability_store"]
    assert sorted(receipt["transformed_fields"]) == ["duration_ms_bucket", "local_turn_id", "request_id"]
    assert receipt["integrity_hash"].startswith("sha256:")


def test_emitted_bundle_files_exist(monkeypatch, tmp_path):
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
        },
    )
    payload_ref = result["catalog_entry"]["payload_ref"].removeprefix("file://")
    event_ref = result["catalog_entry"]["event_ref"].removeprefix("file://")
    receipt_ref = result["catalog_entry"]["receipt_ref"].removeprefix("file://")
    assert Path(payload_ref).exists()
    assert Path(event_ref).exists()
    assert Path(receipt_ref).exists()
    payload = json.loads(Path(payload_ref).read_text(encoding="utf-8"))
    assert payload["event"] == "receipts.citation_resolution.summary"
