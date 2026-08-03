"""Grounding the algebra in the constrained-spectral field theory — the tight links, in code.

The doctrine note (superconscious) claims two correspondences are *identical*, not analogous:

  1. Edgeworth supermodularity (manuscript eq 21) IS the lattice condition our `meet` lives on.
  2. The per-cell clipping projection (manuscript eq 57) IS a `pullback` onto a constraint half-space.

Prose is cheap; this module makes both falsifiable. A 2x2 cell of knot values is the atomic unit on
which supermodularity is enforced. We show the manuscript's cross-difference equals the standard
lattice supermodularity slack `g(a∨b)+g(a∧b) − g(a) − g(b)` with `∧=min` — the very operation
`semantic_algebra.meet` implements — and that the closed-form projection restricts the cell to the
supermodular half-space by the smallest L2 move, which is exactly what `pullback` does abstractly.
"""

from __future__ import annotations

from typing import Dict, Tuple

from procyber.semantic.semantic_algebra import meet

#: A 2x2 cell: value at each corner of the unit square in the (t, u) index lattice.
Corner = Tuple[int, int]
Cell = Dict[Corner, float]

CORNERS: Tuple[Corner, ...] = ((0, 0), (1, 0), (0, 1), (1, 1))


# --------------------------------------------------------------------------- #
# 1. Supermodularity IS the meet-lattice condition
# --------------------------------------------------------------------------- #


def join(a: Corner, b: Corner) -> Corner:
    """Lattice join ∨ = coordinatewise max."""
    return (max(a[0], b[0]), max(a[1], b[1]))


def meet_idx(a: Corner, b: Corner) -> Corner:
    """Lattice meet ∧ = coordinatewise min — the same min-on-a-chain that `meet` uses."""
    return (min(a[0], b[0]), min(a[1], b[1]))


def cross_difference(cell: Cell) -> float:
    """The manuscript's Edgeworth cross-difference (eq 21): supermodular iff >= 0."""
    return cell[(1, 1)] - cell[(1, 0)] - cell[(0, 1)] + cell[(0, 0)]


def lattice_supermodular_slack(cell: Cell) -> float:
    """The standard lattice slack g(a∨b)+g(a∧b) − g(a) − g(b), with a=(1,0), b=(0,1).

    a∨b = (1,1), a∧b = (0,0); so this is g(1,1)+g(0,0) − g(1,0) − g(0,1). It is *equal* to
    `cross_difference` by construction — that equality is the proof that Edgeworth
    complementarity and the meet lattice are one condition (Topkis 1998, Milgrom-Roberts 1990).
    """
    a, b = (1, 0), (0, 1)
    return cell[join(a, b)] + cell[meet_idx(a, b)] - cell[a] - cell[b]


def is_supermodular(cell: Cell) -> bool:
    return cross_difference(cell) >= 0


def is_submodular(cell: Cell) -> bool:
    """Substitutability: the reversed inequality (manuscript eq 23)."""
    return cross_difference(cell) <= 0


def meet_on_chain(x: str, y: str) -> str:
    """The verdict-lattice meet — exposed here to show it is the same min-on-a-chain as ∧."""
    return meet(x, y)  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# 2. The per-cell clipping projection IS a half-space pullback
# --------------------------------------------------------------------------- #

# The supermodularity constraint is aᵀθ ≥ 0 with θ the four corner values and `a` the stencil
# (+1 at (1,1) and (0,0); −1 at (1,0) and (0,1)). Note aᵀθ == cross_difference(θ), and ‖a‖² = 4.
_STENCIL: Dict[Corner, float] = {(1, 1): +1.0, (0, 0): +1.0, (1, 0): -1.0, (0, 1): -1.0}
_STENCIL_NORM2 = sum(v * v for v in _STENCIL.values())  # = 4.0


def project_supermodular(cell: Cell) -> Cell:
    """Project a cell onto the supermodular half-space by the smallest L2 move (eq 57).

    `θ ↦ θ + max(0, −aᵀθ)·a / ‖a‖²`. Idempotent on feasible cells (a `pullback` that admits
    everything already inside), and it lands an infeasible cell exactly on the boundary
    (cross_difference == 0) — the restrictive operator, realised metrically.
    """
    slack = cross_difference(cell)  # = aᵀθ
    step = max(0.0, -slack) / _STENCIL_NORM2
    if step == 0.0:
        return dict(cell)
    return {c: cell[c] + step * _STENCIL[c] for c in CORNERS}


def project_submodular(cell: Cell) -> Cell:
    """Dual projection onto the SUBmodular half-space (substitutability, eq 23)."""
    slack = cross_difference(cell)
    step = max(0.0, slack) / _STENCIL_NORM2
    if step == 0.0:
        return dict(cell)
    return {c: cell[c] - step * _STENCIL[c] for c in CORNERS}
