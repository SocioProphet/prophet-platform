"""The universal receipt sealer — the ONE place the compute plane mints proof.

Backends return raw outputs; the gateway seals. So a Spark job, a notebook cell,
and a graph query all get the identical hash-chained receipt, tamper-evident per
project. (This is the future `libs/receipts` — extracted here as the canonical
owner; lattice-forge keeps its own for its direct path until we unify.)
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Iterator

from . import persistence, signing
from .contract import EpistemicStatus, Receipt

# per-project hash chain — the in-memory structure.
#   persistence DISABLED (tests / ephemeral dev): _CHAINS IS the whole store — seal appends here,
#     reads come from here, and there is nowhere else for a receipt to live.
#   persistence ENABLED (prod): _CHAINS is a BOUNDED LRU cache over the SQLite-backed store. Boot no
#     longer materializes it (see hydrate) — only _TIPS is loaded, O(projects) — so resident memory
#     does not scale with the store. The 2026-08-04 OOM was hydrate() reading EVERY receipt into this
#     dict at import, on top of the hellgraph + embedding libs, OOMKilling the pod ~9s into startup.
#   OrderedDict so the enabled-mode cache can evict least-recently-used projects; tests that call
#   _CHAINS.clear() or index _CHAINS["p"] keep working unchanged (both are OrderedDict operations).
_CHAINS: "OrderedDict[str, list[Receipt]]" = OrderedDict()
_CACHE_MAX_PROJECTS = 64  # enabled-mode cache bound; boot memory is bounded by _TIPS alone


class _Tip:
    """The last receipt id + chain length for one project — all seal() needs to compute the next
    receipt's `prev` and `seq` without the whole chain resident. Loaded O(projects) at boot."""

    __slots__ = ("tip_id", "count")

    def __init__(self, tip_id: str | None, count: int) -> None:
        self.tip_id = tip_id
        self.count = count


# Per-project tips — the authoritative project index in ENABLED mode (loaded at boot, advanced on
# seal). In DISABLED mode this stays empty and _CHAINS is authoritative, so a test's _CHAINS.clear()
# remains a full reset.
_TIPS: dict[str, _Tip] = {}

# per-project seal lock. The seal window (setdefault chain → read prev → attest → append
# → persist) is a read-modify-write on the chain: two concurrent seals for the same
# project used to compute the same `prev`, both append, and both persist under seq=N —
# `INSERT OR REPLACE` in save_receipt then silently dropped one and the chain lost a
# receipt at that position (or worse: the surviving row's `prev` didn't match its
# neighbour, so verify() went `valid: False, reason: "prev-link broken"` after a race).
# The persistence module has its own lock, but it only covers the SQLite write itself,
# not the read of `prev` or the id computation — the window this lock closes.
#
# threading.Lock rather than asyncio.Lock because seal() is sync (called both by
# adapters running in FastAPI's threadpool and by pure-sync callers like config_plane).
# One lock per project so seals for different projects don't serialize against each other.
_LOCKS_LOCK = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def _project_lock(project: str) -> threading.Lock:
    """Get (or create) the per-project seal lock. The double-check pattern keeps the
    common path lock-free once a lock has been minted."""
    lock = _LOCKS.get(project)
    if lock is not None:
        return lock
    with _LOCKS_LOCK:
        lock = _LOCKS.get(project)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[project] = lock
        return lock


def hydrate() -> None:
    """Load ONLY per-project tips (id + count) from durable storage — O(projects), NOT O(receipts).
    Full chains are materialized lazily by chain()/verify() and bounded by the _CHAINS LRU. Idempotent;
    a no-op when persistence is disabled (then _CHAINS is the ephemeral store). This is the fix for the
    2026-08-04 OOM: a restarted process comes up ready to seal and verify with FLAT boot memory no
    matter how large /data has grown, instead of reading the whole store into RAM at import."""
    if not persistence.enabled():
        return
    with _LOCKS_LOCK:
        _TIPS.clear()
        _CHAINS.clear()
        for project, tip_id, count in persistence.load_tips():
            _TIPS[project] = _Tip(tip_id, count)


def _project_names() -> list[str]:
    """Every known project. _TIPS is authoritative when persistence is enabled (loaded at boot +
    advanced on seal); otherwise _CHAINS is the store. Snapshotted under _LOCKS_LOCK so a concurrent
    seal creating a new project cannot change the dict mid-iteration."""
    with _LOCKS_LOCK:
        return list(_TIPS.keys()) if persistence.enabled() else list(_CHAINS.keys())


def _load_chain(project: str) -> list[Receipt]:
    """The project's full chain as the LIVE cached list (callers copy). Cache hit → LRU-touch and
    return. Miss + enabled → materialize from SQLite, cache, evict LRU. Miss + disabled → empty (not
    cached means it does not exist — _CHAINS is the whole store in that mode). Call under the
    per-project lock so a concurrent seal cannot mutate the list during materialization."""
    cached = _CHAINS.get(project)
    if cached is not None:
        _CHAINS.move_to_end(project)
        return cached
    if not persistence.enabled():
        return []
    receipts = [Receipt(**b) for b in persistence.load_project(project)]
    _CHAINS[project] = receipts
    _CHAINS.move_to_end(project)
    while len(_CHAINS) > _CACHE_MAX_PROJECTS:
        _CHAINS.popitem(last=False)  # evict LRU — the durable copy stays in SQLite, the tip in _TIPS
    return receipts


def _read_chain_fresh(project: str) -> list[Receipt]:
    """A chain read that does NOT pollute the LRU cache — for full scans (snapshot_all) that would
    otherwise churn it. From SQLite when enabled, else a copy of the in-memory store."""
    if not persistence.enabled():
        return list(_CHAINS.get(project, []))
    return [Receipt(**b) for b in persistence.load_project(project)]


def sha(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def canonical_size(obj: Any) -> int:
    """Byte size of the SAME canonical serialization sha() hashes — so bytes_in/bytes_out
    (W6.1 exhaust accounting) measure exactly what the content hashes bind."""
    return len(json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode())


def seal(project: str, *, kind: str, backend: str, runtime: str, inputs: Any,
         outputs: Any, status: str, actor: str, epistemic_status: EpistemicStatus,
         bytes_in: int | None = None, bytes_out: int | None = None,
         exhaust_sha: str | None = None) -> Receipt:
    # HOLD the per-project lock across the ENTIRE seal window — setdefault-chain →
    # read-prev → hash body → attest → append → persist — so no two concurrent seals
    # can compute the same `prev`, mint two receipts at the same seq, and race
    # save_receipt's `INSERT OR REPLACE` into silently dropping one. This is the ONLY
    # correct scope: persistence._LOCK covers only the SQLite write itself, so a lock
    # taken there is far too late — the id-hash and the chain position are already
    # committed by the time it runs. Do NOT hold across arbitrary caller code — the
    # window is bounded to hash + attest + persist, all pure/local.
    with _project_lock(project):
        # Read prev + seq for THIS receipt. Enabled: from the O(projects) tip index; the whole chain
        # is never needed to append. Disabled: straight from _CHAINS, which is the store. Either read
        # that MUTATES a dict (creating a new project's entry) is done under _LOCKS_LOCK, because
        # snapshot_all()/_project_names() snapshot the keyset and a concurrent create would otherwise
        # raise `RuntimeError: dictionary changed size during iteration` (Copilot #1106 round 2).
        if persistence.enabled():
            with _LOCKS_LOCK:
                tip = _TIPS.get(project)
            prev = tip.tip_id if tip is not None else None
            seq = tip.count if tip is not None else 0
        else:
            with _LOCKS_LOCK:
                stored = _CHAINS.setdefault(project, [])
            prev = stored[-1].id if stored else None
            seq = len(stored)
        body = {
            "project": project, "kind": kind, "backend": backend, "runtime": runtime,
            "inputs_sha": sha(inputs), "outputs_sha": sha(outputs), "status": status,
            "actor": actor, "epistemic_status": epistemic_status, "prev": prev, "ts": time.time(),
        }
        # exhaust accounting (W6.1) rides OUTSIDE the id-hash body, like the attestation —
        # pre-existing persisted receipts (no such fields) must keep verifying unchanged.
        receipt = Receipt(id=sha(body), **body,
                          bytes_in=bytes_in, bytes_out=bytes_out, exhaust_sha=exhaust_sha)
        # standards-based authenticity, layered on top of the chain's integrity:
        # in-toto Statement v1 + Ed25519 signature (unsigned if no key configured).
        signing.attest(receipt, signing.load_signing_key())
        # write-through AFTER attestation so the durable copy carries the signature/statement, and at
        # the receipt's chain position (seq) so the ordered prev-links reload intact. No-op when disabled.
        persistence.save_receipt(project, seq, receipt.id, receipt.model_dump_json())
        if persistence.enabled():
            # Advance the tip (create-or-replace under _LOCKS_LOCK, safe vs the keyset snapshot), and
            # keep the cache coherent if this project's chain is currently materialized — so a reader
            # holding a cached chain sees the new receipt without a reload.
            with _LOCKS_LOCK:
                _TIPS[project] = _Tip(receipt.id, seq + 1)
            cached = _CHAINS.get(project)
            if cached is not None:
                cached.append(receipt)
                _CHAINS.move_to_end(project)
        else:
            stored.append(receipt)  # disabled: _CHAINS is the store — append the receipt in place
    return receipt


def chain(project: str) -> list[Receipt]:
    """The project's full chain — lazily materialized from SQLite and LRU-cached when persistence is
    enabled; straight from the in-memory store when disabled. Returns a copy."""
    with _project_lock(project):
        return list(_load_chain(project))


def snapshot_all() -> Iterator[tuple[str, list[Receipt]]]:
    """Yield (project, chain) for EVERY project, one at a time, for read-only aggregators like
    /healthz's signed_ratio. A GENERATOR, not a list: peak memory is a single project's chain, not
    O(total receipts) — so the aggregation that folds over the whole store cannot itself reproduce
    the boot-time OOM. Projects are snapshotted under _LOCKS_LOCK (so a concurrent seal creating a
    new project cannot change the set mid-iteration — Copilot #1106), and each chain is read under
    its per-project lock so we never observe one mid-append. Reads bypass the LRU cache so a full
    scan does not churn it."""
    for project in _project_names():
        with _project_lock(project):
            ch = _read_chain_fresh(project)
        yield (project, ch)


def verify(project: str) -> dict:
    """Recompute every id + re-walk every prev-link, and verify every present
    Ed25519 signature. Two independent guarantees: chain integrity (id-hash +
    prev-link) and statement authenticity (signature over the in-toto Statement).

    `signed` reports how many receipts carried a *verifying* signature. A receipt
    that carries a signature which does NOT verify fails the whole check
    (`valid=False`) — a broken signature is tampering, not "unsigned".
    """
    ch = chain(project)  # lazily materialized (cached) when persistence is enabled
    prev: str | None = None
    signed = 0
    for r in ch:
        body = {k: getattr(r, k) for k in (
            "project", "kind", "backend", "runtime", "inputs_sha", "outputs_sha",
            "status", "actor", "epistemic_status", "prev", "ts")}
        if sha(body) != r.id:
            return {"valid": False, "count": len(ch), "signed": signed,
                    "broken_at": r.id, "reason": "id-hash mismatch"}
        if r.prev != prev:
            return {"valid": False, "count": len(ch), "signed": signed,
                    "broken_at": r.id, "reason": "prev-link broken"}
        if r.signature is not None:
            if r.statement is None or not signing.verify_signature(
                    r.statement, r.signature, r.public_key):
                return {"valid": False, "count": len(ch), "signed": signed,
                        "broken_at": r.id, "reason": "signature invalid"}
            signed += 1
        prev = r.id
    return {"valid": True, "count": len(ch), "signed": signed,
            "broken_at": None, "reason": None}


# Boot with whatever durable history exists (no-op when persistence is disabled).
hydrate()
