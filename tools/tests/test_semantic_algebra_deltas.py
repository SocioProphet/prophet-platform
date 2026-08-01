"""Tests for two algebra deltas — both ways.

Delta 1 (Gödel): abstention is a first-class value, BOTTOM, not an out-of-band None.
Delta 3 (Mach + our own discipline): the verdict lattice is DERIVED from what each
verdict clears, not hand-authored — and an un-derivable order is a hard failure.
"""

from __future__ import annotations

import pytest

from tools.semantic_algebra import (
    ACT,
    BOTTOM,
    FST,
    POT,
    SND,
    Abstain,
    LayerError,
    SemanticAddress,
    VERDICT_CLEARS,
    VERDICT_ORDER,
    add,
    bind_tiered,
    derive_verdict_order,
    distance,
    distribute,
    meet,
    mul,
    prim,
    pullback,
)


# --------------------------------------------------------------------------- #
# Delta 1 — BOTTOM as a first-class abstention
# --------------------------------------------------------------------------- #


def test_bottom_is_a_singleton():
    assert Abstain() is BOTTOM
    assert repr(BOTTOM) == "BOTTOM"


def test_grounding_operators_return_bottom_not_none():
    # pullback under a total restriction
    paradigm = distribute(prim(POT), add(prim(FST), prim(SND)))
    assert pullback(paradigm, {"ground": prim(ACT)}) is BOTTOM
    # bind_tiered with no candidate under the anchor
    anchor = mul(prim(POT), prim(FST))
    other = mul(prim(ACT), prim(FST))
    lower = add(mul(other, other))  # sits under `other`, not `anchor`
    assert bind_tiered(anchor, add(anchor, other), lower) is BOTTOM


def test_distance_to_bottom_is_undefined_both_orders():
    t = mul(prim(POT), prim(FST))
    with pytest.raises(LayerError):
        distance(t, BOTTOM)
    with pytest.raises(LayerError):
        distance(BOTTOM, t)


def test_meet_is_absorbing_on_bottom():
    # the ordinary lattice min still holds...
    assert meet("sealed", "weak") == "weak"
    # ...but any undecidable arm makes the reconciliation undecidable
    assert meet("sealed", BOTTOM) is BOTTOM
    assert meet(BOTTOM, "refuse") is BOTTOM
    assert meet(BOTTOM) is BOTTOM


def test_abstaining_address_is_wellformed_but_never_grounded():
    addr = SemanticAddress(term=BOTTOM, iri="kko:Something", inference="abduced")
    assert addr.abstains is True
    # grounded is False EVEN WITH an iri — you cannot ground what you declined to decide
    assert addr.is_grounded is False
    with pytest.raises(LayerError):
        _ = addr.layer
    payload = addr.to_json()
    assert payload["abstains"] is True
    assert payload["code"] == "BOTTOM"
    assert payload["layer"] is None
    assert addr.skeleton()["abstains"] is True


def test_ordinary_address_does_not_abstain():
    addr = SemanticAddress(term=mul(prim(POT), prim(FST)), iri="kko:Thing")
    assert addr.abstains is False
    assert addr.is_grounded is True
    assert addr.layer == 1


# --------------------------------------------------------------------------- #
# Delta 3 — the verdict lattice is derived, not authored
# --------------------------------------------------------------------------- #


def test_derived_order_matches_the_capability_nesting():
    assert VERDICT_ORDER == ("refuse", "quarantine", "weak", "probable", "sealed")


def test_clears_sets_are_strictly_nested():
    for weaker, stronger in zip(VERDICT_ORDER, VERDICT_ORDER[1:]):
        assert VERDICT_CLEARS[weaker] < VERDICT_CLEARS[stronger]  # proper subset


def test_incomparable_verdicts_are_rejected():
    """An un-derivable order is a defect to surface, not to paper over."""
    bad = {
        "a": frozenset(),
        "b": frozenset({"x"}),
        "c": frozenset({"y"}),  # same size as b, incomparable to it
    }
    with pytest.raises(ValueError):
        derive_verdict_order(bad)


def test_a_nested_verdict_extends_the_order_with_no_second_edit():
    extended = dict(VERDICT_CLEARS)
    extended["notarized"] = VERDICT_CLEARS["sealed"] | {"broadcast"}
    order = derive_verdict_order(extended)
    assert order[-1] == "notarized"
    assert order[:-1] == VERDICT_ORDER  # the existing chain is preserved, not rewritten
