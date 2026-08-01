#!/usr/bin/env python3
"""Attention registry (Workspace Control Plane, Phase 4 / D5).

Keeps half-processed work discoverable before it is deeply indexed. Each
`attention-mark.v0` carries a mode, resurfacing triggers, a decay policy, and
suppression rules; this module decides which marks should surface *now*.

Mode semantics:
* **pin**      — always surfaces.
* **watch**    — surfaces when one of its event triggers fires.
* **revisit**  — surfaces at a scheduled time (`at:<iso>` trigger) or on an event.
* **incubate** — surfaces once its decay half-life has elapsed, or on a trigger.
* **hold**     — never surfaces until explicitly released (mode changed).
* **forget**   — never surfaces (tombstoned).

Suppression always wins: if any of a mark's suppression rules is active, it does
not surface regardless of mode.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def should_surface(
    mark: dict[str, Any],
    now: str,
    active_events: Optional[set[str]] = None,
    active_suppressions: Optional[set[str]] = None,
) -> bool:
    """Decide whether a single mark should surface at `now`."""
    active_events = active_events or set()
    active_suppressions = active_suppressions or set()

    mode = mark.get("mode")
    if mode in ("forget", "hold"):
        return False

    # Suppression wins over everything else.
    rules = set(mark.get("suppression", {}).get("rules", []))
    if rules & active_suppressions:
        return False

    if mode == "pin":
        return True

    now_dt = _parse(now)
    triggers = mark.get("resurfacing_triggers", [])
    time_due = any(t.startswith("at:") and _parse(t[3:]) <= now_dt for t in triggers)
    event_due = any((not t.startswith("at:")) and t in active_events for t in triggers)

    if mode == "watch":
        return event_due
    if mode == "revisit":
        return time_due or event_due
    if mode == "incubate":
        decay = mark.get("decay", {})
        half_life = decay.get("half_life_seconds")
        if half_life is not None:
            elapsed = (now_dt - _parse(mark["created_at"])).total_seconds()
            if elapsed >= half_life:
                return True
        return time_due or event_due
    return False


class AttentionRegistry:
    """An in-memory registry of attention marks with resurfacing resolution."""

    def __init__(self) -> None:
        self._marks: dict[str, dict[str, Any]] = {}

    def add(self, mark: dict[str, Any]) -> None:
        self._marks[mark["mark_id"]] = mark

    def release(self, mark_id: str, new_mode: str) -> None:
        """Transition a mark's mode (e.g. release a hold to watch/revisit)."""
        if mark_id in self._marks:
            self._marks[mark_id]["mode"] = new_mode

    def forget(self, mark_id: str) -> None:
        if mark_id in self._marks:
            self._marks[mark_id]["mode"] = "forget"

    def marks(self) -> list[dict[str, Any]]:
        return list(self._marks.values())

    def resolve_surfacing(
        self,
        now: str,
        active_events: Optional[set[str]] = None,
        active_suppressions: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        """Marks that should surface now, in stable (mark_id) order."""
        return [
            m
            for _id, m in sorted(self._marks.items())
            if should_surface(m, now, active_events, active_suppressions)
        ]
