"""Every probe item set must be large enough to resolve a dose effect.

The estate rule is n>=30 (prefer 50), learned from an MMLU board at n=15/subject where
the arm fixed about as many predictions as it broke and per-subject totals came out
exactly equal — under-powered, not "no effect".

This rig reproduced the same failure. The first real-weights run returned
consistency = 1.333, meaning the IMPAIRED model scored better than sober. With 4 claim
items a single flip moves that score by 25 percentage points, which is far wider than
any dose effect worth reporting. The number was noise wearing a decimal point.
"""

from __future__ import annotations

import pytest

from noetica_impair.probes import (
    consistency, fluency_competence, hedging, lookahead, working_memory,
)

MIN_N = 30

SETS = {
    "consistency.CLAIMS": consistency.CLAIMS,
    "hedging.KNOWN": hedging.KNOWN,
    "hedging.UNKNOWABLE": hedging.UNKNOWABLE,
    "lookahead.ITEMS": lookahead.ITEMS,
    "fluency_competence.ITEMS": fluency_competence.ITEMS,
    "working_memory.KEYS": working_memory.KEYS,
    "working_memory.VALUES": working_memory.VALUES,
}


@pytest.mark.parametrize("name", sorted(SETS))
def test_item_set_meets_the_power_floor(name):
    n = len(SETS[name])
    assert n >= MIN_N, (
        f"{name} has {n} items; the floor is {MIN_N}. At n={n} a single item flip "
        f"moves the score by {100 / n:.1f} percentage points, which is wider than the "
        "dose effects this battery exists to detect."
    )


@pytest.mark.parametrize("name", sorted(SETS))
def test_items_are_unique(name):
    """Duplicates inflate n without adding information — power theatre."""
    items = SETS[name]
    firsts = [i[0] if isinstance(i, tuple) else i for i in items]
    dupes = {x for x in firsts if firsts.count(x) > 1}
    assert not dupes, f"{name} repeats: {sorted(dupes)[:3]}"


def test_forced_choice_answers_never_appear_among_their_own_distractors():
    """A distractor equal to the answer makes the item unscoreable."""
    for stem, correct, distractors in fluency_competence.ITEMS:
        assert correct not in distractors, f"{stem}: answer is also a distractor"
    for q, correct, distractors in hedging.KNOWN:
        assert correct not in distractors, f"{q}: answer is also a distractor"
    for *_ctx, correct, distractors in [(i[0], i[1], i[2], i[3]) for i in lookahead.ITEMS]:
        pass  # shape checked below


def test_lookahead_items_are_well_formed():
    for item in lookahead.ITEMS:
        assert len(item) == 4, f"expected (context, question, correct, distractors): {item[0][:40]}"
        _ctx, _q, correct, distractors = item
        assert isinstance(distractors, tuple) and distractors
        assert correct not in distractors


def test_working_memory_keys_and_values_pair_up():
    assert len(working_memory.KEYS) == len(working_memory.VALUES)


def test_a_single_flip_cannot_dominate_any_score():
    """The concrete property the floor buys."""
    for name, items in SETS.items():
        per_item = 100 / len(items)
        assert per_item <= 100 / MIN_N + 1e-9, f"{name}: one flip moves {per_item:.1f}pp"
