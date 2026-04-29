from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.telemetry_runtime import emit_event_bundle, reduce_event  # type: ignore


def test_reduce_event_returns_stable_outcome() -> None:
    outcome = reduce_event(
        "reliability.conversation.stream.completed",
        {
            "request_id": "req-001",
            "local_turn_id": "turn-001",
            "subject_ref": "turn://turn-001",
        },
    )
    assert outcome["event"] == "reliability.conversation.stream.completed"
    assert outcome["action"] in {"ALLOW", "TRANSFORM_ALLOW"}
    assert outcome["subject_ref"] == "turn://turn-001"


def test_emit_event_bundle_returns_bundle_shape() -> None:
    payload = {"subject_ref": "turn://turn-002", "local_turn_id": "turn-002"}
    bundle = emit_event_bundle("telemetry-runtime", "reliability.conversation.stream.completed", payload)
    assert bundle["service"] == "telemetry-runtime"
    assert bundle["outcome"]["event"] == "reliability.conversation.stream.completed"
    assert bundle["payload"] == payload
