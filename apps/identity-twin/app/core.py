"""identity-twin service core — a thin, honest wrapper over the vendored Multiverseal Twin
(`third_party/procyber/semantic`). It consumes the proven library; it reimplements nothing.

HTTP clients speak strings; the twin speaks ℂ^D hypervectors. A value string is encoded to a
hypervector deterministically — `encode_value` seeds a unit-magnitude HV from SHA-256(payload),
the same construction `vrf.reference_hv` uses to seed r_c from a proof. Same payload → same HV;
distinct payloads → near-orthogonal HVs. No raw hypervector ever crosses the HTTP boundary: reads
return compact, verifiable summaries (a reference, a fidelity, a digest, a fringe statistic)."""
from __future__ import annotations

import hashlib
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from procyber.semantic import interferometry as itf
from procyber.semantic import twin as tw
from procyber.semantic import vrf, vsa

SEED_ENV = "IDENTITY_TWIN_SEED"  # 64 hex chars = the sovereign core's 32-byte master key
_MATCH_THRESHOLD = 0.5           # recall fidelity above this = the claimed value matches
_MAX_SNAPSHOTS = 16              # bounded medium-snapshot history for /diff
_EMPTY_DIGEST = "0" * 64


def load_seed() -> bytes | None:
    """The sealed-core seed from the environment (never hardcoded). Absent → an ephemeral random
    master key (dev). Present-but-wrong-length → a hard error, not a silent weak key."""
    raw = os.environ.get(SEED_ENV)
    if not raw:
        return None
    seed = bytes.fromhex(raw)
    if len(seed) != 32:
        raise ValueError(f"{SEED_ENV} must be 32 bytes (64 hex chars), got {len(seed)}")
    return seed


def encode_value(payload: str, d: int) -> vsa.HV:
    """Deterministically encode a value string into a ℂ^D hypervector (SHA-256-seeded, unit
    magnitude, near-orthogonal across distinct payloads)."""
    seed = int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")
    return vsa.random_hv(d, np.random.default_rng(seed))


def digest_hv(hv: vsa.HV) -> str:
    """A stable content fingerprint of a hypervector. Rounding keeps float noise from churning
    the digest while still moving on any real (phase or magnitude) change."""
    return hashlib.sha256(np.round(hv, 9).tobytes()).hexdigest()


@dataclass(frozen=True)
class Reference:
    """The wire form of a `vrf.VerifiableReference` — proof and key hex-encoded."""

    context: str
    proof: str
    verify_key: str

    @classmethod
    def from_vref(cls, ref: vrf.VerifiableReference) -> "Reference":
        return cls(ref.context.decode("utf-8"), ref.proof.hex(), ref.verify_key.hex())

    def to_vref(self) -> vrf.VerifiableReference:
        return vrf.VerifiableReference(
            context=self.context.encode("utf-8"),
            proof=bytes.fromhex(self.proof),
            verify_key=bytes.fromhex(self.verify_key),
        )


class UnknownSnapshot(KeyError):
    """/diff was asked about a medium digest this service never emitted."""


class TwinService:
    """A stateful, in-process Multiverseal Twin surface. The attested medium lives in memory
    (v1 — durable persistence is the next slice); the master key is sealed from the environment."""

    def __init__(self, seed: bytes | None = None) -> None:
        self._twin = tw.MultiversealTwin(seed=seed if seed is not None else load_seed())
        self.d = self._twin.d
        self.verify_key = self._twin.verify_key.hex()
        self._count = 0
        self._snapshots: "OrderedDict[str, vsa.HV]" = OrderedDict()
        self._lock = threading.Lock()

    # ---- write ----
    def attest(self, context: str, value: str) -> tuple[Reference, str, int]:
        """Mint a context reference, bind `value` against it (reference-at-ingest — never bare),
        fold it into the medium, and snapshot the new medium fingerprint."""
        with self._lock:
            ref = self._twin.attest(context.encode("utf-8"), encode_value(value, self.d))
            self._count += 1
            medium = self._twin.medium()  # fresh array (bundle returns a new sum), safe to retain
            digest = digest_hv(medium)
            self._snapshots[digest] = medium
            self._snapshots.move_to_end(digest)
            while len(self._snapshots) > _MAX_SNAPSHOTS:
                self._snapshots.popitem(last=False)
            return Reference.from_vref(ref), digest, self._count

    # ---- reads ----
    def verify(self, ref: Reference) -> bool:
        """True iff the reference's proof verifies. Fail-closed: a malformed reference is
        unverifiable, never a 500."""
        try:
            vref = ref.to_vref()
        except (ValueError, TypeError):
            return False
        return self._twin.verify(vref)

    def recall(self, context: str, claimed_value: str) -> tuple[float, bool]:
        """Fidelity of the recalled value against a claimed value (1.0 = exact). Raises KeyError
        if nothing was attested under `context`."""
        with self._lock:
            recalled = self._twin.recall(context.encode("utf-8"))
        fidelity = vsa.similarity(recalled, encode_value(claimed_value, self.d))
        return fidelity, fidelity >= _MATCH_THRESHOLD

    def medium(self) -> tuple[str, int]:
        """(digest, record_count) — the tamper-evident fingerprint of the federation-facing
        medium, never the raw vector."""
        with self._lock:
            if self._count == 0:
                return _EMPTY_DIGEST, 0
            return digest_hv(self._twin.medium()), self._count

    def diff(self, from_digest: str) -> dict:
        """Interferometric read (§C) between a previously-emitted medium snapshot and the current
        medium — the fringe, not a scalar. Unknown digest → UnknownSnapshot."""
        with self._lock:
            if self._count == 0:
                raise UnknownSnapshot(from_digest)
            current = self._twin.medium()
            to_digest = digest_hv(current)
            if from_digest == to_digest:
                snap = current
            elif from_digest in self._snapshots:
                snap = self._snapshots[from_digest]
            else:
                raise UnknownSnapshot(from_digest)
        fr = itf.fringe(snap, current)
        return {
            "from_digest": from_digest,
            "to_digest": to_digest,
            "changed": bool(itf.is_tampered(snap, current)),
            "phase_energy": itf.phase_energy(snap, current),
            "max_fringe": float(np.max(np.abs(fr))) if fr.size else 0.0,
            "moved_components": int(np.count_nonzero(np.abs(fr) > itf.DEFAULT_TOL)),
            "total_components": int(fr.size),
        }

    def interfere(self, value: str, context_a: str, context_b: str) -> dict:
        """The thesis read: the SAME value bound under two different minted provenances is
        magnitude-identical (a scalar/score read cannot tell them apart) yet has a nonzero phase
        fringe (a fringe read sees the moved provenance). Uses an ephemeral demo core — no state
        mutation, no master-key access."""
        v = encode_value(value, self.d)
        sk, _ = vrf.keygen()
        ref_a = vrf.mint(sk, context_a.encode("utf-8"))
        ref_b = vrf.mint(sk, context_b.encode("utf-8"))
        bound_a = vsa.bind(v, vrf.reference_hv(ref_a.proof, self.d))
        bound_b = vsa.bind(v, vrf.reference_hv(ref_b.proof, self.d))
        mag = itf.magnitude_similarity(bound_a, bound_b)
        energy = itf.phase_energy(bound_a, bound_b)
        return {
            "magnitude_similarity": mag,
            "phase_energy": energy,
            "provenance_moved": bool(itf.provenance_moved(bound_a, bound_b)),
            "score_blind": mag > 0.999,
            "fringe_visible": energy > itf.DEFAULT_TOL,
        }
