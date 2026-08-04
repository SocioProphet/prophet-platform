"""The Multiverseal Twin — the P2 capstone composing the VSA medium (vsa), VRF references (vrf),
and the interferometric read (interferometry) into a federation-facing identity/reputation
projection of a sovereign core.

The sovereign CORE holds a master key (msk); the TWIN is the object that touches the untrusted
world, carries imported reputation, and is watched/replayed by relying parties. Two invariants
from the spec are enforced by construction here:

- **Reference-at-ingest (§B).** A value is admissible only *bound against a VRF-minted context
  reference* — never stored bare. `attest` mints the reference (only the core key can) and folds
  `bind(value, r_c)` into the medium; there is no code path that stores a bare value.
- **Reads are interferometric (§C).** `diff`/`is_tampered` return the fringe between two twin
  states, not a scalar score — phase is provenance.

Everything is proof-carrying: only the core mints (vrf), reconstruction needs the reference
(vsa reference-gated hiding), and any write to the medium is tamper-evident (interferometry).
"""
from __future__ import annotations

import numpy as np

from procyber.semantic import interferometry as itf
from procyber.semantic import vrf, vsa

__all__ = ["MultiversealTwin"]


class MultiversealTwin:
    """A sovereign identity/reputation twin. Construct with an optional 32-byte `seed` for a
    deterministic (sealed) core; otherwise the master key is random."""

    def __init__(self, seed: bytes | None = None, d: int = vrf.DEFAULT_D) -> None:
        self._sk, self.verify_key = vrf.keygen(seed)
        self.d = d
        # context (bytes) -> (VerifiableReference, bound record = bind(value, r_c))
        self._records: dict[bytes, tuple[vrf.VerifiableReference, vsa.HV]] = {}

    def attest(self, context: bytes, value: vsa.HV) -> vrf.VerifiableReference:
        """Ingest an attestation of `value` under `context`. Mints the context reference (only
        this core can), binds the value against it (reference-at-ingest — never bare), and folds
        it into the medium. Returns the verifiable reference relying parties check."""
        if value.shape != (self.d,):
            raise ValueError(f"value must be a ℂ^{self.d} hypervector")
        ref = vrf.mint(self._sk, context)
        r_c = vrf.reference_hv(ref.proof, self.d)
        self._records[context] = (ref, vsa.bind(value, r_c))
        return ref

    def medium(self) -> vsa.HV:
        """The bundled twin state H = Σ bound records — the federation-facing projection. Opaque
        without a reference (a hiding commitment to its contents)."""
        if not self._records:
            raise ValueError("empty twin — nothing attested")
        return vsa.bundle(rec for _, rec in self._records.values())

    def recall(self, context: bytes) -> vsa.HV:
        """Reconstruct the value attested under `context` by illuminating the medium with its
        reference (approximate — carries crosstalk from the other records)."""
        ref, _ = self._records[context]
        return vsa.reconstruct(self.medium(), vrf.reference_hv(ref.proof, self.d))

    def verify(self, ref: vrf.VerifiableReference) -> bool:
        """True iff `ref` is a genuine reference (its proof verifies). Relying parties call this;
        they cannot forge a reference this — or any — twin would accept."""
        return vrf.verify(ref)

    def diff(self, other_medium: vsa.HV) -> np.ndarray:
        """Interferometric read against another twin state — the fringe, not a score (§C)."""
        return itf.fringe(self.medium(), other_medium)

    def is_tampered(self, snapshot: vsa.HV) -> bool:
        """True iff the medium has moved since `snapshot` — holographic tamper-evidence."""
        return itf.is_tampered(snapshot, self.medium())
