from __future__ import annotations

from threading import Lock
from typing import Final

_COUNTERS: dict[str, int] = {
    "academy_ingest_total": 0,
    "search_query_total": 0,
    "academy_result_total": 0,
    "policy_decision_allow_total": 0,
    "policy_decision_deny_total": 0,
    "policy_decision_local_total": 0,
    "policy_decision_remote_total": 0,
    "policy_decision_fallback_total": 0,
}
_LOCK: Final[Lock] = Lock()


def increment(name: str, amount: int = 1) -> None:
    with _LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + amount


def snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_COUNTERS)


def reset() -> None:
    with _LOCK:
        for key in list(_COUNTERS):
            _COUNTERS[key] = 0
