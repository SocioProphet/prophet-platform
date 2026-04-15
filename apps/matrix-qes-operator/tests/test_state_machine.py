from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.state_machine import IncidentThreadState, apply_transition, transition_map  # type: ignore


def test_transition_map_contains_triage() -> None:
    mapping = transition_map()
    assert "triage" in mapping
    assert "ack" in mapping["triage"]


def test_apply_transition_roundtrip() -> None:
    state = apply_transition(IncidentThreadState.TRIAGE, "ack")
    assert state == IncidentThreadState.ACKNOWLEDGED
    state = apply_transition(state, "investigate")
    assert state == IncidentThreadState.INVESTIGATING
    state = apply_transition(state, "replay.request")
    assert state == IncidentThreadState.REPLAY_REQUESTED


def test_invalid_transition_raises() -> None:
    try:
        apply_transition(IncidentThreadState.TRIAGE, "close")
    except ValueError as exc:
        assert "Invalid transition" in str(exc)
    else:
        raise AssertionError("expected invalid transition failure")
