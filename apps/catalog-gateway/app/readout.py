"""Catalog operational plane — analysis layer (the readout).

`ops.py` CAPTURES what the gateway does (one `catalog.*.v0` event per resolve / DCAT
emission). This module FOLDS that event stream into catalog KPIs — the numbers a
steward actually reads: resolve hit/miss, the hot entries, registration candidates
(entries people ask for that don't exist yet), DCAT coverage, and cold sources.

Two entry points, one computation:
  * `compute_readout()` — pure fold over the captured events + the catalog listing.
    Deterministic for a given file-state: given the same events it returns the same
    KPIs (ties broken by id), so it is testable and diffable. `generated_at` is the
    only clock-dependent field and is metadata, not a KPI.
  * `emit_readout()` — crystallizes the readout as a `catalog.ops.readout.v0` event
    into the SAME shared file-state, so the analysis layer is itself observable and a
    downstream SLO gate (WO-2) can read a readout the same way it reads any event.

The readout is derived, not authoritative: it never mutates the catalog or the event
log, and an empty event stream yields a well-formed zero readout (not an error).
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ops
from .store import KINDS, list_ids

SCHEMA_VERSION = "crystal-atlas.catalog.ops.readout.v0"
DEFAULT_TOP_N = 10


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_events() -> list[dict[str, Any]]:
    """Read every captured operational event (best-effort per file). A malformed or
    unreadable event is skipped, never fatal — the readout must survive a partially
    corrupt log rather than blind the steward to the events that ARE readable."""
    d: Path = ops._events_dir()
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(d.glob("*.event.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("event"), dict):
            out.append(obj)
    return out


def _rank(counter: Counter, top_n: int) -> list[tuple[str, int]]:
    # deterministic: count desc, then key asc — never rely on Counter insertion order
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]


def compute_readout(top_n: int = DEFAULT_TOP_N) -> dict[str, Any]:
    events = _load_events()
    resolves = [e["event"] for e in events if e.get("event_type") == "catalog.resolved.v0"]
    dcats = [e["event"] for e in events if e.get("event_type") == "catalog.dcat.emitted.v0"]

    hits = sum(1 for r in resolves if r.get("hit") is True)
    misses = sum(1 for r in resolves if r.get("hit") is False)
    total = hits + misses

    # per-kind resolve breakdown
    by_kind: dict[str, dict[str, int]] = {}
    for r in resolves:
        k = r.get("kind", "unknown")
        b = by_kind.setdefault(k, {"total": 0, "hits": 0, "misses": 0})
        b["total"] += 1
        b["hits"] += 1 if r.get("hit") is True else 0
        b["misses"] += 1 if r.get("hit") is False else 0

    # hot entries (most-resolved) and top misses (registration candidates)
    hot = Counter(f'{r.get("kind","?")}/{r.get("entry_id","?")}' for r in resolves)
    miss_c = Counter(f'{r.get("kind","?")}/{r.get("entry_id","?")}'
                     for r in resolves if r.get("hit") is False)

    def _split(key: str) -> dict[str, str]:
        kind, _, entry_id = key.partition("/")
        return {"kind": kind, "entry_id": entry_id}

    hot_entries = [{**_split(k), "resolves": n} for k, n in _rank(hot, top_n)]
    top_misses = [{**_split(k), "misses": n} for k, n in _rank(miss_c, top_n)]

    # DCAT coverage: distinct assets that emitted a DCAT doc / distinct assets HIT
    dcat_assets = {d.get("asset_id") for d in dcats if d.get("asset_id")}
    resolved_assets = {r.get("entry_id") for r in resolves
                       if r.get("kind") == "asset" and r.get("hit") is True and r.get("entry_id")}
    covered = dcat_assets & resolved_assets
    coverage = round(len(covered) / len(resolved_assets), 4) if resolved_assets else None

    # cold sources: cataloged sources that were never HIT in this window (candidates
    # for deprecation review — they exist but nobody reads them)
    cataloged_sources = set(list_ids("source"))
    hit_sources = {r.get("entry_id") for r in resolves
                   if r.get("kind") == "source" and r.get("hit") is True and r.get("entry_id")}
    cold_sources = sorted(cataloged_sources - hit_sources)

    emitted = [e["event"].get("emitted_at") for e in events if e["event"].get("emitted_at")]
    emitted_sorted = sorted(x for x in emitted if isinstance(x, str))

    return {
        "schema_version": SCHEMA_VERSION,
        "readout_id": "ro_" + uuid.uuid4().hex[:16],
        "generated_at": _now(),
        "producer": ops.PRODUCER,
        "window": {
            "events_scanned": len(events),
            "first_event_at": emitted_sorted[0] if emitted_sorted else None,
            "last_event_at": emitted_sorted[-1] if emitted_sorted else None,
        },
        "resolve": {
            "total": total,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / total, 4) if total else None,
            "by_kind": {k: by_kind[k] for k in sorted(by_kind)},
        },
        "hot_entries": hot_entries,
        "top_misses": top_misses,
        "dcat": {
            "emissions": len(dcats),
            "distinct_assets": len(dcat_assets),
            "coverage_of_resolved_assets": coverage,
        },
        "sources": {
            "cataloged": len(cataloged_sources),
            "read_in_window": len(cataloged_sources & hit_sources),
            "cold": cold_sources,
        },
    }


def emit_readout(top_n: int = DEFAULT_TOP_N) -> tuple[dict[str, Any], str | None]:
    """Compute the readout AND crystallize it as a `catalog.ops.readout.v0` event.
    Returns (readout, event_id). event_id is None if capture is off or the write
    fails — the computed readout is still returned (the fold never depends on the
    write succeeding). Intended for the scheduled readout job / SLO gate (WO-2)."""
    readout = compute_readout(top_n)
    event_id = ops.emit(SCHEMA_VERSION, dict(readout))
    return readout, event_id
