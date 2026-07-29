"""Content-addressed artifact store — the data substrate (Pachyderm/lakeFS answer).

Run lineage says which run produced which receipt. DATA lineage says which exact
bytes flowed through — and lets identical data be stored once and any two runs be
diffed at the data level. Every compute output is put by its content digest
(sha256); identical content dedupes to one blob; the receipt references the
digests. So provenance is not just "run X ran" but "run X consumed blob a…,
produced blob b…", and `diff(run_a, run_b)` is a set operation over digests.

This ships an in-process store (the walking skeleton) behind a `Backend`
interface, so a sovereign persistent backend (zot/MinIO object store — the same
substrate as the sovereign registry) drops in without touching callers.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from . import persistence


def digest(obj: Any) -> str:
    """The content address — sha256 of the canonical JSON encoding."""
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False).encode()
    ).hexdigest()


class Backend(Protocol):
    def put(self, digest: str, blob: Any) -> bool: ...   # True if newly stored, False if already present
    def get(self, digest: str) -> Any | None: ...
    def has(self, digest: str) -> bool: ...


class MemoryBackend:
    """In-process content-addressed blob store. Bounded (FIFO) so it can't grow
    without limit — the persistent backend removes the bound."""

    def __init__(self, max_blobs: int = 4096) -> None:
        self._blobs: dict[str, Any] = {}
        self._max = max_blobs

    def put(self, d: str, blob: Any) -> bool:
        if d in self._blobs:
            return False
        if len(self._blobs) >= self._max:
            self._blobs.pop(next(iter(self._blobs)))
        self._blobs[d] = blob
        return True

    def get(self, d: str) -> Any | None:
        return self._blobs.get(d)

    def has(self, d: str) -> bool:
        return d in self._blobs


class SqliteBackend:
    """Durable content-addressed blob store — survives a restart. Same put/get/has
    contract as MemoryBackend, but blobs live in the gateway SQLite file (unbounded:
    durability is the whole point). zot/MinIO would be one more Backend behind this seam."""

    def put(self, d: str, blob: Any) -> bool:
        if persistence.has_blob(d):
            return False
        persistence.save_blob(d, blob)
        return True

    def get(self, d: str) -> Any | None:
        return persistence.get_blob(d)

    def has(self, d: str) -> bool:
        return persistence.has_blob(d)


_backend: Backend = MemoryBackend()
# receipt id → the ordered artifact digests it produced (the data-lineage index). A cache
# hydrated from durable storage on boot and written through on store_outputs when enabled.
_by_receipt: dict[str, list[str]] = {}
_stats = {"puts": 0, "dedup_hits": 0}


def set_backend(b: Backend) -> None:
    global _backend
    _backend = b


def hydrate() -> None:
    """Point at the durable backend and reload the data-lineage index. No-op when
    persistence is disabled. Called at import so restarts keep full data lineage."""
    if not persistence.enabled():
        return
    set_backend(SqliteBackend())
    _by_receipt.clear()
    _by_receipt.update(persistence.load_index())


def store_outputs(receipt_id: str, outputs: list[Any]) -> list[str]:
    """Put each output by content digest (dedup), index it under the receipt, and
    return the ordered digests."""
    digests: list[str] = []
    for o in outputs:
        d = digest(o)
        newly = _backend.put(d, o)
        _stats["puts"] += 1
        if not newly:
            _stats["dedup_hits"] += 1
        digests.append(d)
    _by_receipt[receipt_id] = digests
    persistence.save_index(receipt_id, digests)   # write-through (no-op when disabled)
    return digests


def put(obj: Any) -> str:
    """Content-address a single blob (dedup'd; durable when persistence is enabled) and
    return its digest. W6.1 uses this for ExhaustRecords so the receipt's exhaust_sha IS
    the retrieval address (/v1/artifacts/{digest})."""
    d = digest(obj)
    newly = _backend.put(d, obj)
    _stats["puts"] += 1
    if not newly:
        _stats["dedup_hits"] += 1
    return d


def get(d: str) -> Any | None:
    return _backend.get(d)


def for_receipt(receipt_id: str) -> list[str]:
    return list(_by_receipt.get(receipt_id, []))


def diff(a_receipt: str, b_receipt: str) -> dict[str, list[str]]:
    """Data-level diff of two runs: which output blobs are shared, added, removed.
    A pure set operation over content digests — reproducibility you can SEE."""
    a = set(_by_receipt.get(a_receipt, []))
    b = set(_by_receipt.get(b_receipt, []))
    return {
        "a": a_receipt, "b": b_receipt,
        "shared": sorted(a & b),
        "added": sorted(b - a),      # in b, not a
        "removed": sorted(a - b),    # in a, not b
        "identical": a == b and bool(a),
    }


def stats() -> dict[str, Any]:
    unique = len({d for ds in _by_receipt.values() for d in ds})
    return {"unique_blobs": unique, "puts": _stats["puts"],
            "dedup_hits": _stats["dedup_hits"], "receipts_indexed": len(_by_receipt)}


def _reset() -> None:   # test hook
    global _backend
    _backend = MemoryBackend()
    _by_receipt.clear()
    _stats.update(puts=0, dedup_hits=0)


# Boot onto durable storage if configured (no-op otherwise).
hydrate()
