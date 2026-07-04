"""Proof-of-Emptiness — erase-as-isomorphism (the Inception Framework's "no silent sinks").

Inception invariant (I2): any morphism X -> ∅ must be an ISOMORPHISM — you cannot
"send to /dev/null". To reach emptiness you must transform X down to a certified
empty form and prove it. Deletion / redaction / quarantine are therefore not
silent sinks but a two-phase iso:

    X --(shred)--> X₀ --(certify H(X₀)=H(∅))--> ∅

This is the deletion-side dual of the ghost audit. The ghost audit proves "no
state CHANGE without an enforced receipt"; Proof-of-Emptiness proves "no state
DELETION without a certified emptiness receipt". Together they close both
directions of no-silent-sinks.

Each type has a distinguished empty value with a FIXED digest (Inception 3.1);
an erasure is valid iff the post-state canonicalizes to exactly that digest.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

SPEC_VERSION = "2.0.0"


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_form(type_name: str) -> Dict[str, Any]:
    """The distinguished empty value for a type (Inception: fixed per schema).

    Unit is not empty: an ack `{}` is NOT ∅. The empty form is explicitly typed
    so "no payload" can never be confused with "empty object".
    """
    return {"__empty__": type_name}


def empty_digest(type_name: str) -> str:
    """H(∅) for a type — the canonical digest the post-state must match."""
    return _sha256(_canonical(empty_form(type_name)))


def shred(obj: Dict[str, Any], type_name: str) -> Dict[str, Any]:
    """Deterministically reduce X to its zero-information variant X₀ (≅ ∅)."""
    return empty_form(type_name)


def prove_emptiness(
    *,
    subject_ref: str,
    object_ref: str,
    type_name: str,
    pre_state: Dict[str, Any],
    post_state: Optional[Dict[str, Any]] = None,
    signer: Any = None,
) -> Dict[str, Any]:
    """Produce a sealed ProofOfEmptiness receipt for an erase-iso.

    If `post_state` is omitted it is produced by `shred`. The receipt is
    `certified` only when the post-state's digest equals H(∅) for the type — an
    uncertified PoE (a silent sink dressed up as a deletion) is emitted with
    certified=false so downstream audit fails it closed.
    """
    if post_state is None:
        post_state = shred(pre_state, type_name)
    pre_d = _sha256(_canonical(pre_state))
    empt_d = empty_digest(type_name)
    post_d = _sha256(_canonical(post_state))
    certified = post_d == empt_d

    receipt: Dict[str, Any] = {
        "id": "urn:srcos:receipt:proof-of-emptiness:" + pre_d.split(":", 1)[1][:24],
        "type": "ProofOfEmptiness",
        "specVersion": SPEC_VERSION,
        "subjectRef": subject_ref,
        "objectRef": object_ref,
        "objectType": type_name,
        "method": "erase-iso",
        "preDigest": pre_d,
        "emptiedDigest": empt_d,
        "postDigest": post_d,
        "certified": certified,
        "issuedAt": _now(),
    }
    from tools.capability_membrane import seal_receipt
    sealed = seal_receipt(receipt)
    if signer is not None:
        sealed = signer.sign_sealed(sealed)
    return sealed


def is_valid_poe(entry: Dict[str, Any]) -> bool:
    """True iff `entry` is a ProofOfEmptiness whose post-state truly reaches ∅."""
    r = entry.get("receipt", entry) if isinstance(entry, dict) else {}
    return (
        r.get("type") == "ProofOfEmptiness"
        and bool(r.get("certified"))
        and r.get("postDigest") == r.get("emptiedDigest")
        and r.get("postDigest") is not None
    )


__all__ = ["empty_form", "empty_digest", "shred", "prove_emptiness", "is_valid_poe"]
