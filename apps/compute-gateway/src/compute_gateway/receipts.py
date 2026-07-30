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
from typing import Any

from . import persistence, signing
from .contract import EpistemicStatus, Receipt

# per-project hash chain — the in-memory index. When GATEWAY_STORE_DIR is set it is a
# cache hydrated from durable storage on boot (see hydrate) and written through on seal,
# so the chain survives a restart; unset, it is the whole store (ephemeral).
_CHAINS: dict[str, list[Receipt]] = {}

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
    """Rebuild the in-memory chains from durable storage. Idempotent; a no-op when
    persistence is disabled. Called at import so a restarted process comes up with its
    full, verifiable history already in hand."""
    if not persistence.enabled():
        return
    _CHAINS.clear()
    for project, bodies in persistence.load_receipts().items():
        _CHAINS[project] = [Receipt(**b) for b in bodies]


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
        chain = _CHAINS.setdefault(project, [])
        prev = chain[-1].id if chain else None
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
        chain.append(receipt)
        # write-through AFTER attestation so the durable copy carries the signature/statement,
        # and at the receipt's chain position so the ordered prev-links reload intact.
        persistence.save_receipt(project, len(chain) - 1, receipt.id, receipt.model_dump_json())
    return receipt


def chain(project: str) -> list[Receipt]:
    return list(_CHAINS.get(project, []))


def snapshot_all() -> list[tuple[str, list[Receipt]]]:
    """A consistent (project, chain) snapshot for read-only aggregators like
    /healthz's signed_ratio. Copilot #1106: iterating `_CHAINS.values()` in the
    server hits `RuntimeError: dictionary changed size during iteration` when a
    concurrent seal() runs setdefault() on a new project. Take the dict snapshot
    under `_LOCKS_LOCK` (which setdefault contends with because _project_lock()
    holds it while creating a new entry) and per-chain snapshots under the
    per-project seal lock so we do not observe a chain mid-append."""
    with _LOCKS_LOCK:
        projects = list(_CHAINS.keys())
    out: list[tuple[str, list[Receipt]]] = []
    for project in projects:
        with _project_lock(project):
            # Copy defensively: the receipt list may have grown or been rebuilt
            # by hydrate() since we snapshotted the keyset.
            out.append((project, list(_CHAINS.get(project, []))))
    return out


def verify(project: str) -> dict:
    """Recompute every id + re-walk every prev-link, and verify every present
    Ed25519 signature. Two independent guarantees: chain integrity (id-hash +
    prev-link) and statement authenticity (signature over the in-toto Statement).

    `signed` reports how many receipts carried a *verifying* signature. A receipt
    that carries a signature which does NOT verify fails the whole check
    (`valid=False`) — a broken signature is tampering, not "unsigned".
    """
    ch = _CHAINS.get(project, [])
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
