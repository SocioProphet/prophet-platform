"""The universal receipt sealer — the ONE place the compute plane mints proof.

Backends return raw outputs; the gateway seals. So a Spark job, a notebook cell,
and a graph query all get the identical hash-chained receipt, tamper-evident per
project. (This is the future `libs/receipts` — extracted here as the canonical
owner; lattice-forge keeps its own for its direct path until we unify.)
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from . import signing
from .contract import EpistemicStatus, Receipt

# per-project hash chain
_CHAINS: dict[str, list[Receipt]] = {}


def sha(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def seal(project: str, *, kind: str, backend: str, runtime: str, inputs: Any,
         outputs: Any, status: str, actor: str, epistemic_status: EpistemicStatus) -> Receipt:
    chain = _CHAINS.setdefault(project, [])
    prev = chain[-1].id if chain else None
    body = {
        "project": project, "kind": kind, "backend": backend, "runtime": runtime,
        "inputs_sha": sha(inputs), "outputs_sha": sha(outputs), "status": status,
        "actor": actor, "epistemic_status": epistemic_status, "prev": prev, "ts": time.time(),
    }
    receipt = Receipt(id=sha(body), **body)
    # standards-based authenticity, layered on top of the chain's integrity:
    # in-toto Statement v1 + Ed25519 signature (unsigned if no key configured).
    signing.attest(receipt, signing.load_signing_key())
    chain.append(receipt)
    return receipt


def chain(project: str) -> list[Receipt]:
    return list(_CHAINS.get(project, []))


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
