"""Abstraction-level gate (S5 instrument) — measure the mismatch the board never did.

The KKO tiered-grounding arm came back inert: grounding fired on 345/350 rows and
moved the score +0.3pp (noise). The lesson was not "grounding is useless" — it was
that nobody measured the quantity grounding was supposed to fix: the
**abstraction-level mismatch rate**, the rate at which an intro-level query is bound
to a graduate-level topic.

This gate measures exactly that over `bind_tiered`, and it has teeth in BOTH
directions, because a one-sided control is not a control:

  * it FAILS if the binder admits a cross-abstraction match (`mismatch_rate` too high);
  * it FAILS as **vacuous** if the binder never admits a correct same-tier match, or
    never abstains on a trap — a binder that abstains on everything scores a perfect
    zero mismatch and is worthless. A control that has only ever passed, or only ever
    fired, is suspect.
  * it FAILS if run below `min_n` — an unfalsifiable sample is not evidence.

`bind_fn` is a parameter so the gate can be pointed at a deliberately broken binder
and shown to catch it; that is the gate's own teeth-both-ways evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from tools.semantic_algebra import Term, TermSet, bind_tiered

BindFn = Callable[[Term, TermSet, TermSet], Optional[Term]]


@dataclass(frozen=True)
class Case:
    """One grounding trial.

    `gold` is the term the binder SHOULD admit, or None when the correct
    behaviour is to abstain (the query has no same-anchor candidate — the trap
    that produced the measured failure).
    """

    name: str
    query: Term
    upper: TermSet
    lower: TermSet
    gold: Optional[Term]

    @property
    def should_admit(self) -> bool:
        return self.gold is not None


@dataclass(frozen=True)
class GateResult:
    n: int
    correct_admits: int
    correct_abstains: int
    mismatches: int          # admitted a term other than gold — the dangerous outcome
    over_abstains: int       # abstained when it should have admitted — a cost, not a danger
    mismatch_rate: float
    admit_rate: float
    passed: bool
    reasons: Sequence[str]


def run_gate(
    cases: Sequence[Case],
    bind_fn: BindFn = bind_tiered,
    *,
    min_n: int = 30,
    max_mismatch_rate: float = 0.0,
) -> GateResult:
    n = len(cases)
    correct_admits = correct_abstains = mismatches = over_abstains = 0

    for case in cases:
        pred = bind_fn(case.query, case.upper, case.lower)
        if pred == case.gold:
            if case.gold is None:
                correct_abstains += 1
            else:
                correct_admits += 1
        elif pred is not None:
            # admitted a binding other than the gold one: bound across the
            # abstraction anchor. This is THE failure being measured.
            mismatches += 1
        else:
            # gold was a term, binder abstained: over-cautious, not unsafe.
            over_abstains += 1

    mismatch_rate = mismatches / n if n else 1.0
    admits = correct_admits + mismatches
    admit_rate = admits / n if n else 0.0

    reasons: List[str] = []
    if n < min_n:
        reasons.append(f"n={n} below min_n={min_n}: sample too small to be evidence")
    if mismatch_rate > max_mismatch_rate:
        reasons.append(
            f"mismatch_rate={mismatch_rate:.3f} exceeds max={max_mismatch_rate:.3f}: "
            f"binder crossed the abstraction anchor {mismatches} time(s)"
        )
    if correct_admits == 0:
        reasons.append("vacuous: binder never admitted a correct same-tier match")
    if correct_abstains == 0:
        reasons.append("vacuous: binder never abstained on a trap — the reject path never fired")

    passed = not reasons
    return GateResult(
        n=n,
        correct_admits=correct_admits,
        correct_abstains=correct_abstains,
        mismatches=mismatches,
        over_abstains=over_abstains,
        mismatch_rate=mismatch_rate,
        admit_rate=admit_rate,
        passed=passed,
        reasons=tuple(reasons),
    )
