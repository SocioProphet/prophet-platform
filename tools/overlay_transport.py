#!/usr/bin/env python3
"""Overlay transport broker (Workspace Control Plane, Phase 6 / D8, D10).

Scaffold-first: the durable Hypercore/Autobase *semantics* — an append-only,
hash-chained log; sparse (lazy subset) fetch; and multiwriter linearization into
one causally-ordered view — implemented in-process with **no network / no Hyper
stack dependency**. Topics are joined only *after* a trust decision
(join-after-trust, D9), conformant to the frozen `topic-manifest.v0`.

When the real Hyper stack is added, swap the local transport behind the same
`OverlayBroker` interface; the pattern registry semantics (§5) do not change.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

KNOWN_TRANSPORTS = {"hypercore", "hyperswarm", "autobase", "hyperdrive"}


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _entry_hash(prev_hash: str, writer: str, seq: int, clock: int, data: str) -> str:
    h = hashlib.blake2b(digest_size=32)
    h.update(f"{prev_hash}|{writer}|{seq}|{clock}|".encode("utf-8"))
    h.update(data.encode("utf-8"))
    return h.hexdigest()


@dataclass
class LogEntry:
    """One append-only entry; `entry_hash` chains it to its predecessor."""

    writer: str
    seq: int
    clock: int  # lamport-style logical clock for causal linearization
    data: str
    prev_hash: str
    entry_hash: str


class AppendLog:
    """A single-writer append-only, hash-chained log (Hypercore semantics)."""

    def __init__(self, writer: str) -> None:
        self.writer = writer
        self.entries: list[LogEntry] = []

    def append(self, data: str, clock: int) -> LogEntry:
        seq = len(self.entries)
        prev = self.entries[-1].entry_hash if self.entries else ""
        e = LogEntry(self.writer, seq, clock, data, prev, _entry_hash(prev, self.writer, seq, clock, data))
        self.entries.append(e)
        return e

    def verify(self) -> bool:
        """True iff the hash chain is intact (tamper-evident)."""
        prev = ""
        for i, e in enumerate(self.entries):
            if e.seq != i or e.prev_hash != prev:
                return False
            if e.entry_hash != _entry_hash(prev, e.writer, e.seq, e.clock, e.data):
                return False
            prev = e.entry_hash
        return True


def sparse_fetch(log: AppendLog, indices: Iterable[int]) -> list[LogEntry]:
    """Fetch only the requested entries (seed_sparse): lazy subset, in order."""
    want = sorted({i for i in indices if 0 <= i < len(log.entries)})
    return [log.entries[i] for i in want]


def linearize(logs: Iterable[AppendLog]) -> list[LogEntry]:
    """Merge multiple writer logs into one causally-ordered view (Autobase).

    Deterministic total order: (clock, writer, seq) — lamport clock first, ties
    broken by writer id then per-writer sequence, so all peers converge.
    """
    all_entries: list[LogEntry] = []
    for log in logs:
        all_entries.extend(log.entries)
    return sorted(all_entries, key=lambda e: (e.clock, e.writer, e.seq))


class OverlayRefused(Exception):
    """Raised when a join/operation is refused; carries structured reasons."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__(", ".join(reasons))
        self.reasons = reasons


@dataclass
class Topic:
    """A joined topic: a set of writer logs sharing a linearized view."""

    name: str
    logs: dict[str, AppendLog] = field(default_factory=dict)

    def writer_log(self, writer: str) -> AppendLog:
        return self.logs.setdefault(writer, AppendLog(writer))


class OverlayBroker:
    """Joins topics after a trust decision and brokers append/fetch/linearize."""

    def __init__(self) -> None:
        self.joined: dict[str, Topic] = {}

    def join(self, manifest: dict, *, trusted: bool, now: str) -> Topic:
        """Join a topic only if trusted, unrevoked, unexpired, known transport."""
        reasons: list[str] = []
        if not trusted:
            reasons.append("untrusted")  # join-after-trust (D9): caller supplies the verdict
        if manifest.get("transport") not in KNOWN_TRANSPORTS:
            reasons.append("unknown_transport")
        rev = manifest.get("revocation") or {}
        if rev.get("revoked"):
            reasons.append("revoked")
        expiry = manifest.get("expiry")
        if expiry and _parse(expiry) <= _parse(now):
            reasons.append("expired")
        if reasons:
            raise OverlayRefused(reasons)
        topic = Topic(manifest["topic"])
        self.joined[manifest["topic"]] = topic
        return topic

    def _require(self, topic: str) -> Topic:
        t = self.joined.get(topic)
        if t is None:
            raise OverlayRefused(["not_joined"])
        return t

    def append(self, topic: str, writer: str, data: str, clock: int) -> LogEntry:
        return self._require(topic).writer_log(writer).append(data, clock)

    def fetch(self, topic: str, writer: str, indices: Iterable[int]) -> list[LogEntry]:
        t = self._require(topic)
        log = t.logs.get(writer)
        return sparse_fetch(log, indices) if log is not None else []

    def linearized_view(self, topic: str) -> list[LogEntry]:
        return linearize(self._require(topic).logs.values())
