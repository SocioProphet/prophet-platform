"""Interferometric diff — the twin's primary read (spec §C): "return the fringe, not the score".

Two clean properties over the ℂ^D VSA medium (vsa.py), both proven in tests/test_interferometry.py:

- **Tamper-evidence.** The medium is holographic, so ANY write perturbs the global phase fringe.
  `is_tampered` detects that the medium changed without needing to know what changed.

- **Fringes, not scores (phase = provenance).** In this algebra the *magnitude* of a record is its
  raw value and the *phase* is who bound it, in what context (spec §1). So a change that preserves
  magnitude but moves phase — the *same value re-attested under a different provenance* — is
  INVISIBLE to a magnitude/score read yet lights up in the fringe. The read layer never collapses
  phase to magnitude, which is exactly the leading-indicator the scalar reputation number misses.

Component-level: `fringe` is nonzero only where two states actually differ, so it doubles as a map
of *where* state moved.
"""
from __future__ import annotations

import numpy as np

from procyber.semantic import vsa

__all__ = ["fringe", "magnitude_similarity", "phase_energy", "is_tampered", "provenance_moved", "DEFAULT_TOL"]

DEFAULT_TOL = 1e-6


def fringe(a: vsa.HV, b: vsa.HV) -> np.ndarray:
    """Elementwise phase difference angle(a ⊙ conj(b)) — the interference pattern. ~0 per
    component where the two states agree, nonzero exactly where state moved (the live map, §C)."""
    return np.angle(a * np.conjugate(b))


def magnitude_similarity(a: vsa.HV, b: vsa.HV) -> float:
    """The phase-BLIND 'score' read: cosine similarity of the magnitude spectra |a|, |b|. This is
    all a scalar reputation number can see — it cannot tell a value apart from its provenance."""
    ma, mb = np.abs(a), np.abs(b)
    na, nb = np.linalg.norm(ma), np.linalg.norm(mb)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(ma, mb) / (na * nb))


def phase_energy(a: vsa.HV, b: vsa.HV) -> float:
    """Mean |fringe| — the magnitude of the phase difference the score read discards."""
    return float(np.mean(np.abs(fringe(a, b))))


def is_tampered(a: vsa.HV, b: vsa.HV, tol: float = DEFAULT_TOL) -> bool:
    """True iff `b` differs from `a` beyond `tol` (in magnitude OR phase). Holographic: a local
    unauthorised write to a bundled medium shows up in the global fringe."""
    return bool(np.max(np.abs(a - b)) > tol)


def provenance_moved(a: vsa.HV, b: vsa.HV, mag_tol: float = 1e-6, phase_tol: float = 1e-6) -> bool:
    """True iff the magnitude spectrum is unchanged but the phase moved — the same value under a
    different provenance. The change a score read is blind to and a fringe read sees (§C, §1)."""
    mag_same = float(np.max(np.abs(np.abs(a) - np.abs(b)))) <= mag_tol
    phase_moved = float(np.max(np.abs(fringe(a, b)))) > phase_tol
    return bool(mag_same and phase_moved)
