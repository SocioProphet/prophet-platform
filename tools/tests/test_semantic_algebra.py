"""Tests for the compositional semantic algebra.

Every gate here is exercised BOTH ways — the pass path and the refusal path.
A guard that has only ever been seen to allow is not evidence of a guard.
"""

from __future__ import annotations

import pytest

from tools.semantic_algebra import (
    ACT,
    BOTTOM,
    DYAD,
    FST,
    MAX_LAYER,
    POT,
    PRIMITIVES,
    SND,
    TRD,
    TRIAD,
    Lexicon,
    LexiconRegistry,
    LayerError,
    SemanticAddress,
    Term,
    add,
    address_distance,
    bind_tiered,
    canonical_json,
    distance,
    distribute,
    meet,
    mul,
    neighbours,
    prim,
    pullback,
    pushout,
)

# --------------------------------------------------------------------------- #
# Primitives and construction
# --------------------------------------------------------------------------- #


def test_generating_set_is_one_neutral_one_dyad_one_triad():
    assert len(PRIMITIVES) == 6
    assert set(DYAD) == {POT, ACT}
    assert set(TRIAD) == {FST, SND, TRD}
    assert set(DYAD) & set(TRIAD) == set()


def test_term_must_be_leaf_or_product_not_both():
    with pytest.raises(ValueError):
        Term(primitive=POT, ground=prim(ACT))
    with pytest.raises(ValueError):
        Term()


def test_unknown_primitive_refused():
    with pytest.raises(ValueError):
        prim("KETER")


# --------------------------------------------------------------------------- #
# The product: non-commutative, layer-graded
# --------------------------------------------------------------------------- #


def test_product_is_non_commutative():
    a, b = prim(POT), prim(ACT)
    assert mul(a, b) != mul(b, a)
    assert mul(a, b).code() != mul(b, a).code()


def test_product_lifts_exactly_one_layer():
    a = mul(prim(POT), prim(ACT))
    assert prim(POT).layer == 0
    assert a.layer == 1
    assert mul(a, a).layer == 2


def test_mixed_layer_product_refused():
    """Layer discipline is enforced at construction, not audited afterwards."""
    low = prim(POT)
    high = mul(prim(POT), prim(ACT))
    with pytest.raises(LayerError):
        mul(low, high)


def test_product_beyond_max_layer_refused():
    term = mul(prim(POT), prim(ACT))
    while term.layer < MAX_LAYER:
        term = mul(term, term)
    assert term.layer == MAX_LAYER
    with pytest.raises(LayerError):
        mul(term, term)


def test_mode_elides_to_neutral_element():
    explicit = mul(prim(POT), prim(ACT), prim("NIL"))
    elided = mul(prim(POT), prim(ACT))
    assert explicit == elided


# --------------------------------------------------------------------------- #
# Addition and distribution — how a paradigm is generated
# --------------------------------------------------------------------------- #


def test_addition_is_commutative_and_normalised():
    a, b = prim(POT), prim(ACT)
    assert add(a, b) == add(b, a)
    assert add(a, b).code() == add(b, a).code()


def test_addition_is_idempotent():
    a = prim(POT)
    assert len(add(a, a)) == 1


def test_addition_across_layers_refused():
    with pytest.raises(LayerError):
        add(prim(POT), mul(prim(POT), prim(ACT)))


def test_paradigm_is_the_product_of_its_variable_roles():
    """A 2x3 root paradigm has exactly six cells — the symmetry group, generated."""
    paradigm = distribute(add(*[prim(p) for p in DYAD]), add(*[prim(p) for p in TRIAD]))
    assert len(paradigm) == 6
    assert all(cell.layer == 1 for cell in paradigm)


def test_distribution_over_addition_holds():
    left = distribute(prim(POT), add(prim(FST), prim(SND)))
    manual = add(mul(prim(POT), prim(FST)), mul(prim(POT), prim(SND)))
    assert left == manual


# --------------------------------------------------------------------------- #
# Distance — computed from form, never learned
# --------------------------------------------------------------------------- #


def test_identical_terms_are_at_distance_zero():
    a = mul(prim(POT), prim(FST))
    assert distance(a, a) == 0


def test_one_role_apart_is_distance_one():
    a = mul(prim(POT), prim(FST))
    b = mul(prim(POT), prim(SND))
    assert distance(a, b) == 1


def test_two_roles_apart_is_farther_than_one():
    base = mul(prim(POT), prim(FST))
    near = mul(prim(POT), prim(SND))
    far = mul(prim(ACT), prim(SND))
    assert distance(base, far) > distance(base, near)


def test_cross_layer_distance_refused():
    with pytest.raises(LayerError):
        distance(prim(POT), mul(prim(POT), prim(ACT)))


def test_neighbours_skips_other_layers_instead_of_coercing():
    target = mul(prim(POT), prim(FST))
    same_layer = mul(prim(POT), prim(SND))
    other_layer = mul(target, target)
    found = neighbours(target, [same_layer, other_layer], radius=1)
    assert same_layer in found
    assert other_layer not in found


# --------------------------------------------------------------------------- #
# The dual operators
# --------------------------------------------------------------------------- #


def test_pullback_restricts_to_matching_cells():
    paradigm = distribute(add(*[prim(p) for p in DYAD]), add(*[prim(p) for p in TRIAD]))
    restricted = pullback(paradigm, {"ground": prim(POT)})
    assert restricted is not None
    assert len(restricted) == 3
    assert all(cell.roles()["ground"] == prim(POT) for cell in restricted)


def test_pullback_abstains_on_total_restriction():
    """A restriction that admits nothing is a first-class abstention, not None."""
    paradigm = distribute(prim(POT), add(prim(FST), prim(SND)))
    assert pullback(paradigm, {"ground": prim(ACT)}) is BOTTOM


def test_pushout_glues_along_a_shared_role():
    a = mul(prim(POT), prim(FST))
    b = mul(prim(POT), prim(SND))
    glued = pushout(a, b, along="ground")
    assert glued.roles()["ground"] == prim(POT)


def test_pushout_refuses_to_glue_over_a_disagreement():
    """Gluing across a disagreement is how contradictory knowledge merges silently."""
    a = mul(prim(POT), prim(FST))
    b = mul(prim(ACT), prim(FST))
    with pytest.raises(ValueError):
        pushout(a, b, along="ground")


def test_pushout_across_layers_refused():
    a = mul(prim(POT), prim(FST))
    b = mul(a, a)
    with pytest.raises(LayerError):
        pushout(a, b, along="ground")


def test_pushout_drops_roles_that_disagree_rather_than_picking_one():
    a = mul(prim(POT), prim(FST))
    b = mul(prim(POT), prim(SND))
    glued = pushout(a, b, along="ground")
    assert glued.roles()["differentia"] not in (prim(FST), prim(SND))


# --------------------------------------------------------------------------- #
# The meet
# --------------------------------------------------------------------------- #


def test_meet_takes_the_weaker_verdict():
    assert meet("sealed", "weak") == "weak"
    assert meet("probable", "refuse") == "refuse"


def test_meet_never_exceeds_either_arm():
    """The property that makes an expansive signal unable to decide on its own."""
    for law in ("refuse", "quarantine", "weak", "probable", "sealed"):
        for evidence in ("refuse", "quarantine", "weak", "probable", "sealed"):
            result = meet(law, evidence)
            assert result in (law, evidence)
            assert result == min((law, evidence), key=("refuse", "quarantine", "weak", "probable", "sealed").index)


def test_meet_is_order_independent():
    assert meet("sealed", "weak") == meet("weak", "sealed")


def test_meet_refuses_unknown_verdicts():
    with pytest.raises(ValueError):
        meet("sealed", "definitely-fine")


# --------------------------------------------------------------------------- #
# Tiered binding — the recorded failure, barred structurally
# --------------------------------------------------------------------------- #


def _tiers():
    """Two anchors with one specific topic injected under each.

    `intro` and `advanced` differ only in their ground anchor, which is exactly
    the situation where a flat vector space picked the wrong abstraction level.
    """
    intro_anchor = mul(prim(POT), prim(FST))
    advanced_anchor = mul(prim(ACT), prim(FST))
    upper = add(intro_anchor, advanced_anchor)
    intro_topic = mul(intro_anchor, mul(prim(POT), prim(SND)))
    advanced_topic = mul(advanced_anchor, mul(prim(ACT), prim(SND)))
    lower = add(intro_topic, advanced_topic)
    return intro_anchor, advanced_anchor, intro_topic, advanced_topic, upper, lower


def test_tiered_binding_descends_through_the_right_anchor():
    intro_anchor, _, intro_topic, _, upper, lower = _tiers()
    assert bind_tiered(intro_anchor, upper, lower) == intro_topic


def test_tiered_binding_bars_the_wrong_abstraction_level():
    """The intro query must NOT reach the advanced topic. This is the whole point."""
    intro_anchor, _, _, advanced_topic, upper, lower = _tiers()
    assert bind_tiered(intro_anchor, upper, lower) != advanced_topic


def test_tiered_binding_abstains_when_nothing_injects():
    intro_anchor, advanced_anchor, _, advanced_topic, upper, _ = _tiers()
    lower_without_intro = add(advanced_topic)
    assert bind_tiered(intro_anchor, upper, lower_without_intro) is BOTTOM


def test_tiered_binding_refuses_a_query_from_the_wrong_layer():
    _, _, _, _, upper, lower = _tiers()
    with pytest.raises(LayerError):
        bind_tiered(prim(POT), upper, lower)


# --------------------------------------------------------------------------- #
# SemanticAddress — intension, extension, warrant
# --------------------------------------------------------------------------- #


def test_address_is_ungrounded_without_an_iri():
    addr = SemanticAddress(term=mul(prim(POT), prim(FST)))
    assert not addr.is_grounded


def test_address_is_grounded_with_an_iri():
    addr = SemanticAddress(term=mul(prim(POT), prim(FST)), iri="kko:Methodeutic")
    assert addr.is_grounded


def test_address_refuses_unknown_inference_type():
    with pytest.raises(ValueError):
        SemanticAddress(term=prim(POT), inference="vibes")


def test_address_refuses_unknown_mood():
    with pytest.raises(ValueError):
        SemanticAddress(term=prim(POT), mood="insinuate")


def test_address_refuses_out_of_range_confidence():
    with pytest.raises(ValueError):
        SemanticAddress(term=prim(POT), confidence=1.5)


def test_skeleton_carries_structure_and_withholds_surface():
    """Structure travels, surface does not — the linkability withhold mechanism."""
    addr = SemanticAddress(
        term=mul(prim(POT), prim(FST)),
        iri="kko:SomeSensitiveConcept",
        evidence_ref="evidence://patient-42",
        confidence=0.9,
    )
    skeleton = addr.skeleton()
    serialised = canonical_json(skeleton)
    assert "code" in skeleton and "layer" in skeleton
    assert "patient-42" not in serialised
    assert "kko:SomeSensitiveConcept" not in serialised


def test_skeleton_still_supports_distance():
    a = SemanticAddress(term=mul(prim(POT), prim(FST)), evidence_ref="secret")
    b = SemanticAddress(term=mul(prim(POT), prim(SND)), evidence_ref="also-secret")
    assert address_distance(a, b) == 1


def test_address_json_omits_absent_warrant_fields():
    addr = SemanticAddress(term=mul(prim(POT), prim(FST)))
    payload = addr.to_json()
    assert "evidenceRef" not in payload
    assert payload["inference"] == "asserted"


# --------------------------------------------------------------------------- #
# Lexicons — a parameter, not a canon
# --------------------------------------------------------------------------- #


def test_registry_resolves_in_priority_order():
    term = mul(prim(POT), prim(FST))
    first = Lexicon("primary", "1.0", {term.code(): "orientation"}, license="Apache-2.0")
    second = Lexicon("fallback", "1.0", {term.code(): "something else"})
    registry = LexiconRegistry([first, second])
    label, source = registry.resolve(term)
    assert label == "orientation"
    assert source.name == "primary"


def test_registry_returns_none_for_uncovered_terms():
    registry = LexiconRegistry([Lexicon("sparse", "1.0", {})])
    assert registry.resolve(mul(prim(POT), prim(FST))) is None


def test_algebra_operates_with_no_lexicon_at_all():
    """Structure is independent of vocabulary — no lexicon is a licensing chokepoint."""
    registry = LexiconRegistry([])
    a = mul(prim(POT), prim(FST))
    b = mul(prim(POT), prim(SND))
    assert registry.resolve(a) is None
    assert distance(a, b) == 1


def test_coverage_is_reported_not_assumed():
    a, b = mul(prim(POT), prim(FST)), mul(prim(POT), prim(SND))
    registry = LexiconRegistry([Lexicon("half", "1.0", {a.code(): "one"})])
    assert registry.coverage([a, b]) == 0.5
