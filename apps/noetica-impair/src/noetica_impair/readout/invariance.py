"""Cross-lab measurement invariance -- what makes a black-box reading defensible.

The problem this solves is specific. A black box cannot be hooked, so to express its
degradation in mechanical units you must locate it on a dose ladder measured somewhere
else. Borrowing ONE lab's ladder is weak: any difference could be the condition under
test, or could be that lab's training pipeline. For Anthropic it is weaker still, since
no open-weight Claude exists and the ladder must come from a different lab entirely.

The move that fixes this is not a better single ruler. It is INVARIANCE.

Measure the same condition on several unrelated white-box models. If the faculty
signature it produces is consistent across all of them -- same faculties hit, same
ordering, comparable magnitudes -- then that signature is a property of the CONDITION
rather than of any lab's pipeline. Only then is it legitimate to locate a black box on
it, because the ruler has been shown not to belong to any particular lab.

This is the standard requirement before comparing latent scores across groups: you
establish that the instrument measures the same thing in each group first. Skipping it
is exactly how "Claude behaves like X" becomes an artifact of whoever's ladder was
convenient.

What this module does NOT license: any claim about a black box's internals. An
invariant behavioural signature transports a BEHAVIOURAL measure. Mechanism is
inferred only where hooks were actually installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from .metrics import FACULTIES, FacultyVector


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _rank(vec: FacultyVector) -> list[str]:
    """Faculties ordered most-damaged first. The SHAPE of the signature."""
    pairs = [(f, float(getattr(vec, f))) for f in FACULTIES]
    return [f for f, _ in sorted(pairs, key=lambda kv: kv[1])]


def _rank_agreement(a: Sequence[str], b: Sequence[str]) -> float:
    """Normalised rank correlation between two faculty orderings (1 = identical)."""
    idx_b = {f: i for i, f in enumerate(b)}
    n = len(a)
    if n < 2:
        return float("nan")
    d2 = sum((i - idx_b.get(f, i)) ** 2 for i, f in enumerate(a))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


@dataclass
class InvarianceReport:
    """Is this condition's signature a property of the condition, or of one lab?"""

    condition: str
    models: list[str]
    per_faculty_spread: dict[str, float]
    mean_rank_agreement: float
    max_faculty_spread: float
    invariant: bool
    reason: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def transportable(self) -> bool:
        """May this signature be used as a ruler for a black-box model?"""
        return self.invariant

    def report(self) -> str:
        head = ("INVARIANT across labs — safe to transport"
                if self.invariant else
                "NOT invariant — this signature belongs to a pipeline, not the condition")
        lines = [f"{head}: {self.condition}",
                 f"  models: {', '.join(self.models)}",
                 f"  {self.reason}"]
        lines += [f"  ! {w}" for w in self.warnings]
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition, "models": list(self.models),
            "per_faculty_spread": dict(self.per_faculty_spread),
            "mean_rank_agreement": round(self.mean_rank_agreement, 4),
            "max_faculty_spread": round(self.max_faculty_spread, 4),
            "invariant": self.invariant, "reason": self.reason,
            "warnings": list(self.warnings),
        }


def check_invariance(
    condition: str,
    per_model: dict[str, FacultyVector],
    *,
    max_spread: float = 0.15,
    min_rank_agreement: float = 0.6,
    min_models: int = 3,
) -> InvarianceReport:
    """Is the faculty signature of ``condition`` stable across white-box models?

    ``per_model`` maps a white-box model key to the retained-fraction FacultyVector
    that condition produced on it. Every vector must already be normalised against its
    OWN sober control -- comparing raw scores across models of different capability
    would measure capability, not the condition.
    """
    models = sorted(per_model)
    warns: list[str] = []
    if len(models) < min_models:
        warns.append(
            f"only {len(models)} model(s); invariance across fewer than {min_models} "
            "cannot distinguish a property of the condition from a property of one lab"
        )

    spread = {
        f: _stdev([float(getattr(per_model[m], f)) for m in models])
        for f in FACULTIES
    }
    max_spread_seen = max(spread.values()) if spread else 0.0

    ranks = [_rank(per_model[m]) for m in models]
    agreements = [
        _rank_agreement(ranks[i], ranks[j])
        for i in range(len(ranks)) for j in range(i + 1, len(ranks))
    ]
    mean_agree = _mean([a for a in agreements if not math.isnan(a)]) if agreements else float("nan")

    magnitude_ok = max_spread_seen <= max_spread
    shape_ok = (not math.isnan(mean_agree)) and mean_agree >= min_rank_agreement
    invariant = bool(magnitude_ok and shape_ok and len(models) >= min_models)

    if invariant:
        reason = (f"faculty ordering agrees at {mean_agree:.2f} across {len(models)} "
                  f"models and no faculty varies by more than {max_spread_seen:.2f}")
    else:
        bits = []
        if not shape_ok:
            worst = max(spread, key=lambda k: spread[k]) if spread else "?"
            bits.append(
                f"faculty ordering agrees only at "
                f"{'n/a' if math.isnan(mean_agree) else f'{mean_agree:.2f}'} "
                f"(needs {min_rank_agreement}) — the models disagree about WHICH "
                f"faculty this condition damages first (widest: {worst})"
            )
        if not magnitude_ok:
            worst = max(spread, key=lambda k: spread[k])
            bits.append(
                f"'{worst}' varies by {spread[worst]:.2f} across models (max "
                f"{max_spread}) — the magnitude is pipeline-specific"
            )
        if len(models) < min_models:
            bits.append(f"only {len(models)} model(s)")
        reason = "; ".join(bits)

    return InvarianceReport(
        condition=condition, models=models, per_faculty_spread=spread,
        mean_rank_agreement=mean_agree, max_faculty_spread=max_spread_seen,
        invariant=invariant, reason=reason, warnings=tuple(warns),
    )


@dataclass
class BlackBoxReading:
    """A black-box result, carrying the provenance of the ruler it was read against."""

    target: str
    condition: str
    faculty: FacultyVector
    reference_models: list[str]
    kinship: str
    invariance: InvarianceReport | None
    scoring_mode: str
    defensible: bool
    caveats: tuple[str, ...] = field(default_factory=tuple)

    def report(self) -> str:
        head = "DEFENSIBLE" if self.defensible else "NOT DEFENSIBLE AS STATED"
        lines = [
            f"{head}: {self.target} under {self.condition}",
            f"  ruler: {', '.join(self.reference_models) or '(none)'} "
            f"[kinship={self.kinship}, instrument={self.scoring_mode}]",
        ]
        lines += [f"  ! {c}" for c in self.caveats]
        return "\n".join(lines)


def read_black_box(
    *,
    target: str,
    condition: str,
    faculty: FacultyVector,
    invariance: InvarianceReport | None,
    kinship: str,
    scoring_mode: str,
    reference_models: Sequence[str] = (),
) -> BlackBoxReading:
    """Assemble a black-box reading with every weakness attached to it.

    A reading is defensible only when the signature was shown INVARIANT across
    unrelated white-box models. Without that, the number still exists -- it is just a
    comparison against one pipeline, and says so.
    """
    caveats: list[str] = []
    defensible = True

    if invariance is None:
        defensible = False
        caveats.append(
            "no invariance check was run: this locates the target on ONE lab's ladder, "
            "so any difference may be that pipeline rather than the condition"
        )
    elif not invariance.invariant:
        defensible = False
        caveats.append(f"the reference signature is not invariant — {invariance.reason}")

    if kinship == "none_available":
        caveats.append(
            "no open-weight model exists from this lab, so the ruler is another lab's. "
            "Invariance is what makes that acceptable; without it the reading is not "
            "calibrated to this vendor at all"
        )
    elif kinship == "unrelated":
        caveats.append("the ruler is from an unrelated lab; prefer the vendor's own "
                       "open-weights model where one exists")

    caveats.append(
        "BEHAVIOURAL ONLY: no hooks were installed in the target. This transports a "
        "behavioural measure and licenses no claim about the target's internals"
    )
    return BlackBoxReading(
        target=target, condition=condition, faculty=faculty,
        reference_models=list(reference_models), kinship=kinship,
        invariance=invariance, scoring_mode=scoring_mode,
        defensible=defensible, caveats=tuple(caveats),
    )
