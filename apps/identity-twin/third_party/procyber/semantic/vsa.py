"""Vector-symbolic algebra (VSA) — the continuous ℂ^D substrate for the Multiverseal Twin.

This is the CONTINUOUS layer that complements this package's discrete, symbolic algebra
(`semantic_algebra.py`: Term / meet / SemanticAddress). The Multiverseal-Twin spec needs a
holographic medium — "a linear medium holding many near-orthogonal patterns, opaque without
a reference, reconstructed by illuminating with that reference" — which the discrete algebra
does not provide. This module supplies it.

Method: unit-magnitude complex Holographic Reduced Representations (Plate, "Holographic
Reduced Representations", 1995 — an academic construction in the public domain). A hypervector
lives in ℂ^D with every component on the unit circle (e^{iθ}); phase carries the relation
(who bound what, in which context — "phase = provenance" in the twin spec). Three operators:

    bind(a, b)      elementwise product  a ⊙ b        (record object a against reference b)
    unbind(c, b)    elementwise  c ⊙ conj(b)          (illuminate with the reference)
    bundle(v_1..n)  superpose (sum)                    (many records in one medium)

Because components are unit-magnitude, conj(b) is the EXACT inverse of b under bind, so
unbind(bind(a,b), b) == a. Reconstruction from a bundle is approximate: unbind(H, r_j)
returns o_j plus crosstalk from the other terms, whose phases are random and sum to noise —
which is exactly the reference-gated hiding + graceful-degradation the twin spec relies on.

Proven in tests/test_vsa.py: (1) reference-gated hiding & reconstruction, (2) the ε/JL
capacity bound (fidelity degrades ~1/√N and stays clean sub-threshold, never catastrophic).
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

__all__ = [
    "random_hv",
    "bind",
    "unbind",
    "bundle",
    "similarity",
    "bundle_bound",
    "reconstruct",
]

HV = np.ndarray  # a complex128 vector in ℂ^D, unit-magnitude components


def random_hv(d: int, rng: np.random.Generator) -> HV:
    """A random unit-magnitude hypervector in ℂ^D (each component e^{iθ}, θ~U(0,2π))."""
    theta = rng.uniform(0.0, 2.0 * np.pi, size=d)
    return np.exp(1j * theta)


def bind(a: HV, b: HV) -> HV:
    """Record `a` against reference `b` (elementwise product; stays unit-magnitude)."""
    return a * b


def unbind(c: HV, b: HV) -> HV:
    """Illuminate `c` with reference `b` (elementwise product with the conjugate = inverse)."""
    return c * np.conjugate(b)


def bundle(vectors: Iterable[HV]) -> HV:
    """Superpose records into one medium (sum). NOT unit-magnitude — it is a hiding
    commitment to its contents; reconstruction needs the reference (see `reconstruct`)."""
    acc = None
    for v in vectors:
        acc = v.copy() if acc is None else acc + v
    if acc is None:
        raise ValueError("bundle() requires at least one vector")
    return acc


def similarity(a: HV, b: HV) -> float:
    """Real part of the normalised Hermitian inner product — 1.0 identical, ~0 orthogonal."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.real(np.vdot(a, b)) / (na * nb))


def bundle_bound(pairs: Sequence[tuple[HV, HV]]) -> HV:
    """Build the twin medium H = Σ_k bind(object_k, reference_k) from (object, reference) pairs."""
    return bundle(bind(o, r) for o, r in pairs)


def reconstruct(medium: HV, reference: HV) -> HV:
    """Illuminate the bundled medium with a reference to recover the object bound under it
    (plus crosstalk). similarity(reconstruct(H, r_j), o_j) is high; a wrong reference yields
    noise — the public-twin / private-reconstruction primitive."""
    return unbind(medium, reference)
