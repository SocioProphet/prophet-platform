"""Tests that ground the algebra in the constrained-spectral field theory — both ways.

The point is falsifiability: the doctrine claims supermodularity IS the meet lattice and the
per-cell clipping IS a pullback. These tests make those claims fail if they were ever untrue.
"""

from __future__ import annotations

import math

import pytest

from tools.semantic_algebra import VERDICT_ORDER, meet
from tools.spectral_grounding import (
    CORNERS,
    cross_difference,
    is_submodular,
    is_supermodular,
    lattice_supermodular_slack,
    meet_idx,
    project_submodular,
    project_supermodular,
)


def _cell(v00, v10, v01, v11):
    return {(0, 0): v00, (1, 0): v10, (0, 1): v01, (1, 1): v11}


# -- 1. supermodularity IS the lattice condition (the identity) -------------- #


@pytest.mark.parametrize(
    "cell",
    [
        _cell(0, 1, 1, 3),     # supermodular: cross-diff = +1
        _cell(0, 2, 2, 3),     # submodular:   cross-diff = -1
        _cell(1, 1, 1, 1),     # modular:      cross-diff = 0
        _cell(-2, 0.5, 4, -7), # arbitrary
    ],
)
def test_cross_difference_equals_lattice_slack(cell):
    # Edgeworth cross-difference == g(a∨b)+g(a∧b) − g(a) − g(b). This equality is the proof.
    assert math.isclose(cross_difference(cell), lattice_supermodular_slack(cell))


def test_the_meet_used_is_the_min_on_a_chain():
    # the lattice ∧ on the index chain {0<1} is min...
    assert meet_idx((1, 0), (0, 1)) == (0, 0)
    # ...and the verdict `meet` is the same min-on-a-chain: weaker of the two wins.
    assert meet(VERDICT_ORDER[3], VERDICT_ORDER[1]) == VERDICT_ORDER[1]
    assert meet(VERDICT_ORDER[0], VERDICT_ORDER[4]) == VERDICT_ORDER[0]


def test_supermodular_and_submodular_classification():
    assert is_supermodular(_cell(0, 1, 1, 3)) and not is_submodular(_cell(0, 1, 1, 3))
    assert is_submodular(_cell(0, 2, 2, 3)) and not is_supermodular(_cell(0, 2, 2, 3))
    modular = _cell(1, 1, 1, 1)
    assert is_supermodular(modular) and is_submodular(modular)  # the shared boundary


# -- 2. the per-cell clipping IS a half-space pullback ----------------------- #


def test_projection_is_a_noop_on_feasible_cells():
    cell = _cell(0, 1, 1, 3)  # already supermodular
    assert project_supermodular(cell) == cell


def test_projection_lands_an_infeasible_cell_exactly_on_the_boundary():
    cell = _cell(0, 2, 2, 3)  # cross-diff = -1, infeasible
    projected = project_supermodular(cell)
    # the restrictive operator makes it exactly feasible (boundary), not over-corrected
    assert math.isclose(cross_difference(projected), 0.0, abs_tol=1e-12)


def test_projection_is_the_minimal_l2_move():
    cell = _cell(0, 2, 2, 3)
    projected = project_supermodular(cell)
    slack = cross_difference(cell)  # = -1
    # closed form: each corner moves by |slack|/4 along the stencil sign
    moved = sum((projected[c] - cell[c]) ** 2 for c in CORNERS)
    assert math.isclose(moved, slack * slack / 4.0)  # = ‖max(0,−aᵀθ)·a/‖a‖²‖²


def test_projection_idempotent():
    cell = _cell(0, 3, 3, 1)  # strongly submodular
    once = project_supermodular(cell)
    twice = project_supermodular(once)
    assert once == twice  # a pullback applied to its own output is a no-op


def test_submodular_projection_is_the_dual():
    cell = _cell(0, 1, 1, 5)  # supermodular; project onto the SUBmodular half-space
    projected = project_submodular(cell)
    assert math.isclose(cross_difference(projected), 0.0, abs_tol=1e-12)
    # a modular cell is fixed by both projections (the shared face)
    modular = _cell(1, 1, 1, 1)
    assert project_supermodular(modular) == modular == project_submodular(modular)
