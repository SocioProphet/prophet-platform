"""Tests for the abstraction-level gate.

The gate must PASS the real structural binder and FAIL two broken ones — a
naive binder that ignores the abstraction anchor, and a lazy binder that
abstains on everything. Proving both is the gate's own teeth-both-ways evidence:
a gate that only ever passes is not measuring anything.
"""

from __future__ import annotations

from typing import List, Optional

from tools.semantic_algebra import (
    PRIMITIVES,
    Term,
    TermSet,
    add,
    bind_tiered,
    mul,
    prim,
)
from tools.abstraction_level_gate import Case, run_gate


def _pair_cases() -> List[Case]:
    """Reproduce the intro->graduate trap across >=30 distinct anchor pairs.

    For each ordered pair of distinct grounds (a, c):
      intro_anchor = a . FST      grad_anchor = c . FST
      C_intro = intro_anchor squared   (a layer-2 topic UNDER the intro anchor)
      C_grad  = grad_anchor squared    (a layer-2 topic UNDER the grad anchor)

    * admit case  — query at the intro anchor, both topics offered; the correct
      binding is C_intro, never C_grad.
    * abstain case — query at the grad anchor, only the intro topic offered; the
      correct behaviour is to abstain rather than bind a grad query to an
      intro topic. This is the trap that produced the measured failure.
    """
    b = prim("FST")
    cases: List[Case] = []
    for a in PRIMITIVES:
        for c in PRIMITIVES:
            if a == c:
                continue
            intro_anchor = mul(prim(a), b)
            grad_anchor = mul(prim(c), b)
            c_intro = mul(intro_anchor, intro_anchor)
            c_grad = mul(grad_anchor, grad_anchor)
            upper = add(intro_anchor, grad_anchor)
            cases.append(
                Case(
                    name=f"admit:{a}->intro",
                    query=intro_anchor,
                    upper=upper,
                    lower=add(c_intro, c_grad),
                    gold=c_intro,
                )
            )
            cases.append(
                Case(
                    name=f"abstain:{c}-grad-vs-intro-only",
                    query=grad_anchor,
                    upper=upper,
                    lower=add(c_intro),  # no candidate under the grad anchor
                    gold=None,
                )
            )
    return cases


# -- the real binder passes at n >= 30 -------------------------------------- #


def test_real_binder_passes():
    cases = _pair_cases()
    assert len(cases) >= 30
    result = run_gate(cases, bind_fn=bind_tiered)
    assert result.passed, result.reasons
    assert result.mismatch_rate == 0.0
    assert result.correct_admits > 0
    assert result.correct_abstains > 0


# -- a binder that ignores the anchor is CAUGHT (dangerous direction) -------- #


def _naive_bind(query: Term, upper: TermSet, lower: TermSet) -> Optional[Term]:
    """Ignores the abstraction anchor entirely — always returns some lower term."""
    return sorted(lower.terms, key=lambda t: t.code())[0]


def test_naive_binder_fails_on_mismatch():
    result = run_gate(_pair_cases(), bind_fn=_naive_bind)
    assert not result.passed
    assert result.mismatches > 0
    assert any("mismatch_rate" in r for r in result.reasons)


# -- a binder that abstains on everything is CAUGHT as vacuous --------------- #


def _lazy_bind(query: Term, upper: TermSet, lower: TermSet) -> Optional[Term]:
    return None


def test_lazy_binder_fails_as_vacuous():
    result = run_gate(_pair_cases(), bind_fn=_lazy_bind)
    assert not result.passed
    assert result.mismatches == 0  # it never admits anything...
    assert any("vacuous" in r for r in result.reasons)  # ...which is exactly the failure


# -- an under-sized run is not evidence ------------------------------------- #


def test_below_min_n_fails():
    result = run_gate(_pair_cases()[:5], bind_fn=bind_tiered, min_n=30)
    assert not result.passed
    assert any("below min_n" in r for r in result.reasons)


# -- the named intro-physics / graduate-QFT trap, spelled out --------------- #


def test_intro_query_never_binds_to_graduate_topic():
    mechanics = mul(prim("ACT"), prim("FST"))   # intro anchor
    qft = mul(prim("TRD"), prim("FST"))         # graduate anchor
    qft_topic = mul(qft, qft)                   # a topic under the graduate anchor
    upper = add(mechanics, qft)
    lower = add(qft_topic)                       # only a graduate topic on offer

    # An intro-level query finds no topic under its own anchor -> abstains,
    # rather than matching the graduate topic (the 0.38-0.54 cosine failure).
    assert bind_tiered(mechanics, upper, lower) is None
    # ...whereas a binder that ignored the anchor would wrongly bind it:
    assert _naive_bind(mechanics, upper, lower) == qft_topic
