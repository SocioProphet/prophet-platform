"""Governed notebook SCHEDULING — Databricks-Jobs parity, but proof-carrying.

A schedule is a cell (or notebook) pinned to a recurring interval. Every run is
executed through the SAME governed path an interactive cell takes — the run
seals a hash-chained receipt (see receipts.seal) — so a scheduled job is exactly
as tamper-evident and replayable as one a human triggered. The difference is who
pulls the trigger: a Kubernetes CronJob hits POST /v1/run-due once a minute, and
this store decides which schedules are due.

Kept pure and in-memory (v1): a plain dict keyed by schedule id, no wall-clock
reads inside the store (`now` is always injected in the hot paths) so it is fully
testable. State is pod-local — like the kernels in execn — so the forge runs a
single replica and `due()`/`mark_ran()` never race across pods.
"""
from __future__ import annotations

import time

from . import receipts

# keep a handle to the builtin: `list` below is the public schedule-list function.
_list = list

# minimum interval — a floor on how hot a governed job may run (the CronJob ticks
# once a minute anyway, so anything under this can never fire faster in practice).
MIN_INTERVAL_SECONDS = 30

# in-memory schedule store (v1). id -> schedule. Persistence = follow-up.
_SCHEDULES: dict[str, dict] = {}


def create(project: str, name: str, code: str, interval_seconds: int, *,
           language: str = "python", adapter: str | None = None,
           session_id: str | None = None, now: float | None = None) -> dict:
    """Register a recurring governed job. First run is due one interval from now."""
    now = time.time() if now is None else now
    sid = receipts.new_id()
    schedule = {
        "id": sid, "project": project, "name": name, "code": code,
        "language": language, "adapter": adapter,
        # default to a per-schedule kernel so scheduled runs don't collide with a
        # user's interactive `<project>:default` session (they can opt into sharing).
        "session_id": session_id or f"{project}:sched:{sid}",
        "interval_seconds": interval_seconds,
        "next_run": now + interval_seconds, "last_run": None, "last_status": None,
        "created_at": now, "enabled": True,
    }
    _SCHEDULES[sid] = schedule
    return schedule


def list(project: str) -> _list[dict]:
    return [s for s in _SCHEDULES.values() if s["project"] == project]


def get(sid: str) -> dict | None:
    return _SCHEDULES.get(sid)


def delete(sid: str) -> bool:
    return _SCHEDULES.pop(sid, None) is not None


def due(now: float | None = None) -> _list[dict]:
    """Enabled schedules whose next_run has arrived — what the CronJob fires."""
    now = time.time() if now is None else now
    return [s for s in _SCHEDULES.values() if s["enabled"] and s["next_run"] <= now]


def mark_ran(sid: str, status: str, now: float | None = None) -> dict | None:
    """Record a run and advance next_run by one interval.

    Advance from the scheduled `next_run`, not from `now`, so a late tick (the
    CronJob is best-effort) doesn't let cadence drift; if we've fallen more than a
    full interval behind, snap forward past `now` to avoid a thundering catch-up.
    """
    now = time.time() if now is None else now
    s = _SCHEDULES.get(sid)
    if s is None:
        return None
    s["last_run"] = now
    s["last_status"] = status
    nxt = s["next_run"] + s["interval_seconds"]
    while nxt <= now:
        nxt += s["interval_seconds"]
    s["next_run"] = nxt
    return s
