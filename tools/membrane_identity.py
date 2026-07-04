"""IdentityRoot — the single sovereign identity that threads the three layers.

One DID that (a) roots attestation on the twin (SPIRE SVID reference), (b) mints
capability tokens (the gapi/OAuth "capability minting" plane), and (c) signs the
membrane's sealed receipt (the CAIRN_COMMIT). Wiring one identity through all
three turns the wire → decision → ground stack into a single verifiable chain,
and gives "breach" (hard identity rotation) something concrete to rotate.

    DID (did:key, Ed25519)
      ├── svid_ref     → SPIRE/SVID attestation on the immutable twin (R0 root)
      ├── mint_cap_token → CapabilityToken issuer (sourceos-spec shape)
      └── sign_sealed  → Ed25519 signature over the sealed AgentMachineReceipt

Signing is ADDITIVE: the capability-membrane kernel stays pure/stdlib-only and
emits valid unsigned receipts; when an IdentityRoot is supplied it attaches a
detached `ed25519:<base64url>` signature over the sourceos FOG preimage
(SRCOS-FOG-V1\\n<type>\\n<id>\\n<payload-hash>). Requires the `cryptography`
package; absent it, HAVE_CRYPTO is False and signing helpers raise clearly so
callers can skip rather than emit a fake signature.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

try:  # real crypto if available; never fabricate a signature without it
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    HAVE_CRYPTO = True
except Exception:  # pragma: no cover - exercised only on stripped envs
    HAVE_CRYPTO = False

# multicodec varint prefix for an Ed25519 public key (0xed 0x01)
_ED25519_MULTICODEC = b"\xed\x01"
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + out


def _b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + body


def did_key_from_pubkey(pubkey: bytes) -> str:
    """did:key encoding for an Ed25519 public key (multibase base58btc, 'z')."""
    return "did:key:z" + _b58encode(_ED25519_MULTICODEC + pubkey)


def pubkey_from_did_key(did: str) -> bytes:
    if not did.startswith("did:key:z"):
        raise ValueError(f"not a did:key: {did!r}")
    raw = _b58decode(did[len("did:key:z"):])
    if not raw.startswith(_ED25519_MULTICODEC):
        raise ValueError("did:key is not an Ed25519 key")
    return raw[len(_ED25519_MULTICODEC):]


def fog_preimage(obj_type: str, obj_id: str, payload_hash: str) -> bytes:
    """sourceos FOG domain-separated preimage (FOG_ENVELOPE_CANONICALIZATION)."""
    return f"SRCOS-FOG-V1\n{obj_type}\n{obj_id}\n{payload_hash}".encode("utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class IdentityRoot:
    """A sovereign signing identity. Generate fresh, or restore from a 32-byte seed."""
    _sk: Any = field(default=None, repr=False)
    svid_ref: Optional[str] = None          # urn:srcos:svid:... (SPIRE attestation on the twin)
    _did: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not HAVE_CRYPTO:
            raise RuntimeError("cryptography not available — cannot mint a signing identity")
        if self._sk is None:
            self._sk = Ed25519PrivateKey.generate()
        self._did = did_key_from_pubkey(self.public_key_bytes)

    @classmethod
    def from_seed(cls, seed: bytes, svid_ref: Optional[str] = None) -> "IdentityRoot":
        if not HAVE_CRYPTO:
            raise RuntimeError("cryptography not available")
        if len(seed) != 32:
            raise ValueError("seed must be 32 bytes")
        return cls(_sk=Ed25519PrivateKey.from_private_bytes(seed), svid_ref=svid_ref)

    @property
    def public_key_bytes(self) -> bytes:
        from cryptography.hazmat.primitives import serialization
        return self._sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    @property
    def did(self) -> str:
        return self._did

    # -- signing -------------------------------------------------------------
    def sign(self, data: bytes) -> str:
        return "ed25519:" + _b64u(self._sk.sign(data))

    def sign_sealed(self, sealed: Dict[str, Any]) -> Dict[str, Any]:
        """Attach a detached signature over the sealed record's FOG preimage.

        The preimage binds to the record's sealHash (which already binds the
        receipt), so the signature is tamper-evident against any mutation of the
        receipt, the seal, or the identity.
        """
        payload_hash = sealed.get("sealHash") or _sha256_hex(_canonical(sealed))
        preimage = fog_preimage(sealed.get("type", "SealedReasoningEvidence"), sealed.get("id", ""), payload_hash)
        signed = dict(sealed)
        signed["signerDid"] = self.did
        signed["svidRef"] = self.svid_ref
        signed["signedAt"] = _now()
        signed["signature"] = self.sign(preimage)
        return signed

    # -- capability minting (gapi/OAuth "capability minting" plane) -----------
    def mint_cap_token(
        self,
        *,
        subject_id: str,
        operations: Sequence[str],
        ttl_seconds: int = 900,
        dataset_ids: Sequence[str] = (),
        decision_ref: str = "urn:srcos:decision:membrane",
    ) -> Dict[str, Any]:
        """Issue a sourceos-spec CapabilityToken, signed by this identity.

        Mirrors the gapi cap_token = f(AgentContract, user policy, time window):
        scoped, short-lived, and bound to the issuing DID.
        """
        body = {
            "tokenId": "urn:srcos:capability-token:" + hashlib.sha256(
                f"{self.did}|{subject_id}|{time.time_ns()}".encode()
            ).hexdigest()[:24],
            "subject": {"subjectId": subject_id, "kind": "agent"},
            "scope": {"operations": list(operations), "datasetIds": list(dataset_ids)},
            "purpose": "capability-invocation",
            "decisionRef": decision_ref,
            "iss": self.did,
            "exp": int(time.time()) + ttl_seconds,
        }
        body["signature"] = self.sign(fog_preimage("CapabilityToken", body["tokenId"], _sha256_hex(_canonical(body))))
        return body


def verify_sealed(sealed: Dict[str, Any]) -> bool:
    """Recompute the FOG preimage and verify the detached Ed25519 signature."""
    if not HAVE_CRYPTO:
        raise RuntimeError("cryptography not available — cannot verify")
    sig = sealed.get("signature")
    did = sealed.get("signerDid")
    if not sig or not did or not sig.startswith("ed25519:"):
        return False
    payload_hash = sealed.get("sealHash") or ""
    preimage = fog_preimage(sealed.get("type", "SealedReasoningEvidence"), sealed.get("id", ""), payload_hash)
    try:
        pub = Ed25519PublicKey.from_public_bytes(pubkey_from_did_key(did))
        pub.verify(base64.urlsafe_b64decode(sig[len("ed25519:"):] + "=="), preimage)
        return True
    except Exception:
        return False


@dataclass
class IdentityChain:
    """The DID → SVID → issuer → signer binding, as a declarable contract.

    This is the small artifact that ties the twin's R0 (SPIRE attestation of an
    immutable OSTree node) to the membrane's receipt: everything downstream is
    anchored to `did`, and a breach = rotating `did` + `svid_ref` and refusing
    to promote anything not signed by the new root.
    """
    did: str
    svid_ref: Optional[str] = None          # SPIRE SVID on the twin (R0 attestation)
    issuer: bool = True                     # may mint capability tokens
    receipt_signer: bool = True             # may sign membrane receipts
    approved_hashes_ref: Optional[str] = None  # ApprovedHashes Merkle-log anchor (breach lineage)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "IdentityChain",
            "specVersion": "0.1.0",
            "did": self.did,
            "svidRef": self.svid_ref,
            "roles": {"issuer": self.issuer, "receiptSigner": self.receipt_signer},
            "approvedHashesRef": self.approved_hashes_ref,
        }


__all__ = [
    "HAVE_CRYPTO",
    "IdentityRoot",
    "IdentityChain",
    "did_key_from_pubkey",
    "pubkey_from_did_key",
    "fog_preimage",
    "verify_sealed",
]
