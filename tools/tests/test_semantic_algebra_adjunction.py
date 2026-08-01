"""Proof obligations P1-P6 for the layer adjunction lift ⊣ ground — both ways.

Each law is pinned on its refusal path too: a coreflection asserted but never shown to
reject is not a coreflection. See docs/SEMANTIC_LAYER_ADJUNCTION.md.
"""

from __future__ import annotations

import pytest

from tools.semantic_algebra import (
    BOTTOM,
    FST,
    MAX_LAYER,
    POT,
    SND,
    LayerError,
    _neutral_at,
    distance,
    distance_bridged,
    ground,
    lift,
    mul,
    prim,
    refines,
)


def _l1():
    return mul(prim(POT), prim(FST))  # a layer-1 term


def _l1b():
    return mul(prim(POT), prim(SND))  # a different layer-1 term


# -- P1: layers move by exactly one; lifting past MAX_LAYER is refused --------- #


def test_p1_layers_and_the_ceiling():
    t = _l1()
    assert lift(t).layer == t.layer + 1
    assert ground(lift(t)).layer == t.layer
    # refusal: lifting a top-layer term would exceed the ceiling
    top = t
    while top.layer < MAX_LAYER:
        top = lift(top)
    with pytest.raises(LayerError):
        lift(top)


# -- P2: ground ∘ lift = id (section); ground of a leaf abstains --------------- #


def test_p2_section_and_leaf_abstains():
    for t in (prim(POT), _l1(), lift(_l1())):
        assert ground(lift(t)) == t
    # refusal: a primitive stands on nothing
    assert ground(prim(FST)) is BOTTOM


# -- P3: p ⊑ lift(ground(p)) (closure); a non-refinement is rejected ---------- #


def test_p3_closure_and_its_refusal():
    p = mul(_l1(), _l1b())  # layer 2, ground = _l1()
    assert refines(p, lift(ground(p)))
    # refusal: a term on a different ground does NOT refine lift(ground(p))
    other = mul(_l1b(), _l1b())
    assert not refines(other, lift(ground(p)))


# -- P4: monotonicity, both a passing and a failing premise ------------------- #


def test_p4_monotonicity():
    a = mul(prim(POT), prim(FST))
    b = mul(prim(POT), _neutral_at(0))  # more general: differentia neutralized
    assert refines(a, b)  # a ⊑ b
    assert refines(lift(a), lift(b))  # ...so lift preserves it
    # refusal: distinct pinned differentiae are NOT a refinement either way
    c = mul(prim(POT), prim(SND))
    assert not refines(a, c)
    assert not refines(c, a)


# -- P5: the Galois condition ground(y) ⊑ x ⟺ y ⊑ lift(x) --------------------- #


def test_p5_galois_equivalence():
    x = _l1()
    lift_x = lift(x)
    candidates = [
        mul(x, _l1b()),        # ground = x  -> both sides True
        mul(_l1b(), _l1b()),   # ground != x -> both sides False
        mul(x, x),             # ground = x  -> both sides True
    ]
    for y in candidates:
        left = refines(ground(y), x)
        right = refines(y, lift_x)
        assert left == right, y.code()


# -- P6: the bridge is the ONLY legal crossing -------------------------------- #


def test_p6_bridge_is_the_only_crossing():
    lo = _l1()
    hi = mul(lo, _l1b())  # layer 2, adjacent
    # the warranted crossing is defined and non-negative
    d = distance_bridged(lo, hi)
    assert isinstance(d, int) and d >= 0
    # raw cross-layer distance still raises — the bridge did not weaken the bar
    with pytest.raises(LayerError):
        distance(lo, hi)
    # same-layer is not a bridge
    with pytest.raises(LayerError):
        distance_bridged(lo, _l1b())
    # non-adjacent (n -> n+2) is refused
    hi2 = mul(hi, hi)  # layer 3
    with pytest.raises(LayerError):
        distance_bridged(lo, hi2)


# -- the refinement relation itself is pinned both ways ----------------------- #


def test_refinement_relation_positive_and_negative():
    a = mul(prim(POT), prim(FST))
    top = _neutral_at(1)
    assert refines(a, top)          # everything refines the top
    assert refines(a, a)            # reflexive
    assert not refines(top, a)      # the top refines nothing below it
    with pytest.raises(LayerError):
        refines(prim(POT), a)       # cross-layer is undefined
