"""Verifiable references for the Multiverseal Twin — mint/verify asymmetry (spec §D).

Only the sovereign core (holding the master secret) can MINT a valid context reference;
any relying party (holding the verify key) can VERIFY one and cannot forge it. This is the
twin's trust anchor: "anyone verifies, essentially no one mints" (the passport/banknote
master/replica structure).

Realised as a deterministic-signature verifiable-unpredictable function (VUF): the proof is
an Ed25519 signature over the context (FIPS 186-5 approved; Ed25519 is deterministic ⇒ the
proof is unique per (key, context)), and the context reference r_c is the ℂ^D hypervector
seeded by SHA-256(proof) (FIPS 180-4). Because the signature cannot be produced without the
master key, r_c cannot be computed without it — and forging a valid (context, proof) reduces
to forging Ed25519 (twin spec §D reduction theorem). The FIPS-approved primitives keep this
inside the estate's crypto boundary.

The reference r_c is a proper unit-magnitude hypervector, so it binds/unbinds directly in the
VSA twin medium (vsa.py): the high-entropy, near-orthogonal reference §A/§1 assumed.

Rigor note: a deterministic-signature VUF gives mint-asymmetry + uniqueness + unforgeability
— what the twin needs. Strict VRF pseudorandomness (RFC 9381 ECVRF) is a drop-in upgrade
behind this same interface if a later use requires it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from procyber.semantic import vsa

DEFAULT_D = 1024

__all__ = ["VerifiableReference", "keygen", "mint", "verify", "reference_hv", "context_reference"]


@dataclass(frozen=True)
class VerifiableReference:
    """A minted context reference: the context, the Ed25519 proof, and the raw verify key."""

    context: bytes
    proof: bytes          # Ed25519 signature over `context`
    verify_key: bytes     # raw 32-byte Ed25519 public key


def keygen(seed: bytes | None = None) -> tuple[ed25519.Ed25519PrivateKey, bytes]:
    """Return (master signing key, raw verify key). If `seed` (32 bytes) is given the key is
    deterministic — for reproducible tests and sealed cores; otherwise it is random."""
    if seed is not None:
        if len(seed) != 32:
            raise ValueError("seed must be exactly 32 bytes")
        sk = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    else:
        sk = ed25519.Ed25519PrivateKey.generate()
    return sk, sk.public_key().public_bytes_raw()


def mint(sk: ed25519.Ed25519PrivateKey, context: bytes) -> VerifiableReference:
    """Mint a verifiable reference for `context`. Only the holder of `sk` can do this."""
    proof = sk.sign(context)  # deterministic ⇒ unique per (key, context)
    return VerifiableReference(context=context, proof=proof, verify_key=sk.public_key().public_bytes_raw())


def verify(ref: VerifiableReference) -> bool:
    """True iff `ref.proof` is a genuine Ed25519 signature of `ref.context` under `ref.verify_key`."""
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(ref.verify_key).verify(ref.proof, ref.context)
        return True
    except (InvalidSignature, ValueError):
        return False


def reference_hv(proof: bytes, d: int = DEFAULT_D) -> vsa.HV:
    """The ℂ^D context reference r_c derived from a proof — deterministic, high-entropy,
    near-orthogonal. Minter and verifier both compute the same r_c from the proof."""
    seed = int.from_bytes(hashlib.sha256(proof).digest()[:8], "big")
    return vsa.random_hv(d, np.random.default_rng(seed))


def context_reference(ref: VerifiableReference, d: int = DEFAULT_D) -> vsa.HV:
    """Verify, then derive r_c — fail-closed: refuses to produce a reference from an
    unverified proof (a forged or tampered reference yields no usable r_c)."""
    if not verify(ref):
        raise ValueError("reference does not verify — refusing to derive r_c")
    return reference_hv(ref.proof, d)
