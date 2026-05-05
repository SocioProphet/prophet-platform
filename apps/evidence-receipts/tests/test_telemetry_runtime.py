from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.telemetry_runtime import emit_event_bundle, reduce_event  # type: ignore


def _completed_stream_payload() -> dict:
    return {
        "request_id": "req-001",
        "local_turn_id": "turn-001",
        "duration_ms_bucket": 6400,
        "stream_transport": "sse_like",
        "completion_status": "clean_final_message",
        "subject_ref": "turn://turn-001",
        "created_at": "2026-05-04T21:01:00+00:00",
    }


def test_reduce_event_returns_stable_outcome() -> None:
    outcome = reduce_event("reliability.conversation.stream.completed", _completed_stream_payload())
    assert outcome["event"] == "reliability.conversation.stream.completed"
    assert outcome["action"] == "TRANSFORM_ALLOW"
    assert outcome["subject_ref"] == "turn://turn-001"
    assert outcome["fields"]["duration_ms_bucket"] == "5s_to_10s"


def test_emit_event_bundle_returns_reduced_bundle_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    bundle = emit_event_bundle("telemetry-runtime", "reliability.conversation.stream.completed", _completed_stream_payload())
    assert bundle["service"] == "telemetry-runtime"
    assert bundle["outcome"]["event"] == "reliability.conversation.stream.completed"
    assert bundle["payload"]["event"] == "reliability.conversation.stream.completed"
    assert bundle["payload"]["plane"] == "reliability"
    assert bundle["payload"]["fields"]["duration_ms_bucket"] == "5s_to_10s"
    assert bundle["receipt"]["status"] == "recorded"
