from __future__ import annotations

from enum import Enum


class IncidentThreadState(str, Enum):
    NEW = "new"
    TRIAGE = "triage"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    REPLAY_REQUESTED = "replay_requested"
    REPLAY_RUNNING = "replay_running"
    SUPPRESSED = "suppressed"
    RESOLVED = "resolved"
    CLOSED = "closed"


TRANSITIONS: dict[IncidentThreadState, dict[str, IncidentThreadState]] = {
    IncidentThreadState.NEW: {"thread.created": IncidentThreadState.TRIAGE},
    IncidentThreadState.TRIAGE: {
        "ack": IncidentThreadState.ACKNOWLEDGED,
        "resolve": IncidentThreadState.RESOLVED,
    },
    IncidentThreadState.ACKNOWLEDGED: {
        "investigate": IncidentThreadState.INVESTIGATING,
        "resolve": IncidentThreadState.RESOLVED,
    },
    IncidentThreadState.INVESTIGATING: {
        "replay.request": IncidentThreadState.REPLAY_REQUESTED,
        "suppress": IncidentThreadState.SUPPRESSED,
        "resolve": IncidentThreadState.RESOLVED,
    },
    IncidentThreadState.REPLAY_REQUESTED: {
        "replay.approve": IncidentThreadState.REPLAY_RUNNING,
        "replay.reject": IncidentThreadState.INVESTIGATING,
        "cancel": IncidentThreadState.INVESTIGATING,
    },
    IncidentThreadState.REPLAY_RUNNING: {
        "replay.finished": IncidentThreadState.INVESTIGATING,
        "replay.failed": IncidentThreadState.INVESTIGATING,
    },
    IncidentThreadState.SUPPRESSED: {
        "unsuppress": IncidentThreadState.INVESTIGATING,
        "resolve": IncidentThreadState.RESOLVED,
    },
    IncidentThreadState.RESOLVED: {
        "close": IncidentThreadState.CLOSED,
        "reopen": IncidentThreadState.INVESTIGATING,
    },
    IncidentThreadState.CLOSED: {"reopen": IncidentThreadState.INVESTIGATING},
}


def apply_transition(current: IncidentThreadState, action: str) -> IncidentThreadState:
    allowed = TRANSITIONS.get(current, {})
    if action not in allowed:
        raise ValueError(f"Invalid transition from {current.value!r} using action {action!r}")
    return allowed[action]


def transition_map() -> dict[str, list[str]]:
    return {state.value: sorted(actions.keys()) for state, actions in TRANSITIONS.items()}
