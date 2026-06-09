"""
Retry policy resolution for zone publication outcomes.

Determines whether a failed publication attempt is terminal, and computes
backoff timing for the next eligible retry. Retry policy is additive — it
does not replace the existing failure evidence path or retry state tracking.

A terminal attempt writes a dead-letter artifact and sets retry_eligible=False.
A non-terminal attempt sets retry_eligible=True and records next_retry_not_before.

This module contains no I/O, no filesystem operations, and no transport logic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_RETRY_POLICY: dict[str, Any] = {
    "max_attempts": 3,
    "retry_backoff_seconds": 30,
    "retry_strategy": "fixed",
    "dead_letter_on_terminal": True,
}


def resolve_retry_policy(record: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve the retry policy for a publication record.

    Falls back to DEFAULT_RETRY_POLICY if the record does not specify one.
    Values in the record's retry_policy override the defaults.
    """
    policy = dict(DEFAULT_RETRY_POLICY)
    record_policy = record.get("retry_policy") or {}
    if isinstance(record_policy, dict):
        policy.update(record_policy)
    return policy


def is_terminal_attempt(attempt: int, policy: dict[str, Any]) -> bool:
    """
    Return True if this attempt number is the last permitted attempt.

    An attempt is terminal when attempt >= max_attempts.
    """
    return attempt >= policy.get("max_attempts", DEFAULT_RETRY_POLICY["max_attempts"])


def compute_next_retry_not_before(attempt: int, policy: dict[str, Any]) -> str | None:
    """
    Compute an ISO 8601 timestamp indicating when the next retry may run.

    Returns None when the attempt is terminal (no retry should be scheduled).
    """
    if is_terminal_attempt(attempt, policy):
        return None
    strategy = policy.get("retry_strategy", "fixed")
    base_seconds = int(policy.get("retry_backoff_seconds", DEFAULT_RETRY_POLICY["retry_backoff_seconds"]))
    if strategy == "exponential":
        delay_seconds = base_seconds * (2 ** (attempt - 1))
    else:
        # fixed (default) and anything unrecognised → fixed
        delay_seconds = base_seconds
    not_before = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    return not_before.replace(microsecond=0).isoformat()
