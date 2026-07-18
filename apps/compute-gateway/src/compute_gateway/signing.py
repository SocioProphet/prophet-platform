"""Standards-based attestation for the universal receipt.

The hash-chain (receipts.py) proves *integrity* (tamper-evidence within a
project). This module adds *authenticity* on open, interoperable rails:

  • in-toto Statement v1  — the receipt rendered as a supply-chain attestation
    (https://in-toto.io/Statement/v1), so any in-toto verifier can consume it.
  • Ed25519 signature      — over the canonical statement bytes, key from env
    `GATEWAY_SIGNING_KEY` (base64 32-byte seed). No key → unsigned (never faked).
  • Nanopublication        — the attested claim as a minimal signed nanopub
    (assertion / provenance / pubinfo / signature). Full RDF/TriG is a noted
    follow-up; the JSON here is a correct, signable skeleton.

Keyless (Sigstore/Fulcio) signing is a flagged follow-up — we keep the seam
(`signature` + `public_key`) so swapping the key source is local.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .contract import Receipt

IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://socioprophet.dev/ComputeResult/v1"


def canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON encoding — the exact bytes we sign and verify."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def load_signing_key() -> Ed25519PrivateKey | None:
    """Ed25519 private key from `GATEWAY_SIGNING_KEY` (base64 32-byte seed).

    Absent or malformed → None (the caller emits an *unsigned* receipt; we never
    fabricate a signature).
    """
    raw = os.getenv("GATEWAY_SIGNING_KEY", "").strip()
    if not raw:
        return None
    try:
        seed = base64.b64decode(raw)
        if len(seed) != 32:
            return None
        return Ed25519PrivateKey.from_private_bytes(seed)
    except Exception:  # noqa: BLE001 — a bad key is treated as "no key", never faked
        return None


def _pub_b64(pub: Ed25519PublicKey) -> str:
    from cryptography.hazmat.primitives import serialization
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def in_toto_statement(receipt: Receipt) -> dict[str, Any]:
    """Render a sealed receipt as an in-toto Statement v1.

    The subject digest is the raw hex of the outputs hash (in-toto digests carry
    no `sha256:` prefix — the algorithm is the map key).
    """
    outputs_hex = receipt.outputs_sha.split(":", 1)[-1]
    return {
        "_type": IN_TOTO_STATEMENT_TYPE,
        "subject": [{
            "name": f"compute:{receipt.kind}:{receipt.backend}",
            "digest": {"sha256": outputs_hex},
        }],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "kind": receipt.kind,
            "backend": receipt.backend,
            "runtime": receipt.runtime,
            "inputs_sha": receipt.inputs_sha,
            "outputs_sha": receipt.outputs_sha,
            "epistemic_status": receipt.epistemic_status,
            "actor": receipt.actor,
            "ts": receipt.ts,
            "prev": receipt.prev,
        },
    }


def sign_statement(statement: dict[str, Any],
                   key: Ed25519PrivateKey | None) -> tuple[str | None, str | None]:
    """(signature_b64, public_key_b64) over canonical statement bytes, or (None, None)."""
    if key is None:
        return None, None
    sig = key.sign(canonical_bytes(statement))
    return base64.b64encode(sig).decode(), _pub_b64(key.public_key())


def verify_signature(statement: dict[str, Any], signature_b64: str | None,
                     public_key_b64: str | None) -> bool:
    """True iff the Ed25519 signature verifies against the canonical statement bytes."""
    if not signature_b64 or not public_key_b64:
        return False
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        pub.verify(base64.b64decode(signature_b64), canonical_bytes(statement))
        return True
    except (InvalidSignature, Exception):  # noqa: BLE001
        return False


def attest(receipt: Receipt, key: Ed25519PrivateKey | None) -> Receipt:
    """Attach the in-toto statement + Ed25519 signature to a sealed receipt.

    Mutates and returns the receipt. Excluded from the id-hash, so the chain is
    untouched. No key → statement present, signature/public_key None (unsigned).
    """
    statement = in_toto_statement(receipt)
    sig, pub = sign_statement(statement, key)
    receipt.statement = statement
    receipt.signature = sig
    receipt.public_key = pub
    return receipt


def nanopublication(receipt: Receipt, key: Ed25519PrivateKey | None) -> dict[str, Any]:
    """A minimal signed Nanopublication for an attested compute claim.

    Correct JSON skeleton with the four canonical graphs (assertion / provenance
    / pubinfo / signature). Full RDF/TriG serialization is a flagged follow-up.
    """
    np_uri = f"np:compute:{receipt.id.split(':', 1)[-1][:16]}"
    assertion = {
        "@id": f"{np_uri}#assertion",
        "subject": receipt.outputs_sha,
        "predicate": "sp:epistemicStatus",
        "object": receipt.epistemic_status,
    }
    provenance = {
        "@id": f"{np_uri}#provenance",
        "prov:wasGeneratedBy": f"compute:{receipt.kind}:{receipt.backend}",
        "prov:generatedAtTime": receipt.ts,
        "prov:wasAttributedTo": receipt.actor,
        "sp:receipt": receipt.id,
    }
    pubinfo = {
        "@id": f"{np_uri}#pubinfo",
        "sp:kind": receipt.kind,
        "sp:backend": receipt.backend,
        "sp:runtime": receipt.runtime,
        "prov:generatedAtTime": receipt.ts,
    }
    body = {"assertion": assertion, "provenance": provenance, "pubinfo": pubinfo}
    sig, pub = sign_statement(body, key)
    return {
        **body,
        "signature": {
            "@id": f"{np_uri}#signature",
            "algorithm": "Ed25519",
            "signature": sig,
            "public_key": pub,
        },
    }
