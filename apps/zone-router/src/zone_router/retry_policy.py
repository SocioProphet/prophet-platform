from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_RETRY_POLICY = {
    "version": "0.1",
    "max_attempts": 3,
    "backoff_seconds": 60,
    "strategy": "fixed",
    "dead_letter_on_terminal": True,
}


def resolve_retry_policy(record: dict[str, Any]) -> dict[str, Any]:
    policy = dict(DEFAULT_RETRY_POLICY)
    override = record.get("retry_policy")
    if isinstance(override, dict):
        for key in DEFAULT_RETRY_POLICY:
            if key in override and override[key] is not None:
                policy[key] = override[key]
    policy["max_attempts"] = int(policy["max_attempts"])
    policy["backoff_seconds"] = int(policy["backoff_seconds"])
    policy["dead_letter_on_terminal"] = bool(policy["dead_letter_on_terminal"])
    policy["strategy"] = str(policy["strategy"])
    return policy


def is_terminal_attempt(attempt: int, policy: dict[str, Any]) -> bool:
    return int(attempt) >= int(policy["max_attempts"])


def compute_next_retry_not_before(attempt: int, policy: dict[str, Any]) -> str | None:
    if is_terminal_attempt(attempt, policy):
        return None
    backoff = int(policy["backoff_seconds"])
    if str(policy.get("strategy", "fixed")) == "exponential":
        backoff = backoff * (2 ** max(int(attempt) - 1, 0))
    return (datetime.now(timezone.utc) + timedelta(seconds=backoff)).replace(microsecond=0).isoformat()
