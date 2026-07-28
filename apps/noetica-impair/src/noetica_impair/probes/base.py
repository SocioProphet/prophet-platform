"""Probe plumbing. Probes are DRIVER-AGNOSTIC (invariant 0.2).

A probe never touches a model, hooks, or a dose. It is handed a ``Subject`` -- an
object that turns a prompt into text and scores continuations -- and returns a
``ProbeResult``. That is what lets the identical battery measure a mechanical lesion
and a charged-topic prompt, which is the whole basis of the equivalence mapping in
section 7. If a probe ever needed to know which driver produced its subject, the
headline result would be circular.

Item sets are fixed, seeded and versioned; changing one bumps ``battery_version``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


#: How a forced choice is resolved. This is an INSTRUMENT, and two results measured
#: with different instruments are not comparable — see readout.parity.
#:   "logprob"    -- score both continuations; needs white-box or a logprob API
#:   "generative" -- present the options and parse the answer; works on any black box
SCORING_MODES = ("logprob", "generative")


class Subject(Protocol):
    """What a driver hands to the battery."""

    def generate(self, prompt: str, *, max_new_tokens: int = 64) -> str: ...

    def loglikelihood(self, prompt: str, continuation: str) -> float: ...


def scoring_modes(subject: Any) -> tuple[str, ...]:
    """Which instruments this subject supports, most precise first."""
    declared = getattr(subject, "supported_scoring_modes", None)
    if declared is not None:          # an explicitly EMPTY list means "none", not "sniff"
        return tuple(declared)
    has_ll = callable(getattr(subject, "loglikelihood", None))
    return ("logprob", "generative") if has_ll else ("generative",)


def common_scoring_mode(*subjects: Any) -> str:
    """The most precise instrument ALL subjects support.

    A white-box model and an API model must be measured the same way or the comparison
    is between instruments rather than between models. Since logprobs are usually
    unavailable on a black box, the pair is normally negotiated DOWN to generative --
    which means the white-box reference is deliberately measured less precisely than it
    could be. That is the cost of a fair comparison, and it is paid on purpose.
    """
    sets = [set(scoring_modes(s)) for s in subjects]
    shared = set.intersection(*sets) if sets else set()
    for mode in SCORING_MODES:
        if mode in shared:
            return mode
    raise ValueError(
        "no shared scoring mode across subjects: "
        + ", ".join(str(sorted(x)) for x in sets)
        + " -- these cannot be compared on the same standard"
    )


@dataclass
class ProbeResult:
    name: str
    score: float                                  # higher = better, raw (not retained)
    detail: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)


class Probe(abc.ABC):
    name: str = "probe"
    version: str = "v1"

    @abc.abstractmethod
    def run(self, subject: Subject) -> ProbeResult: ...


def choose(subject: Subject, prompt: str, options: Sequence[str], *,
           mode: str | None = None, seed: int = 0, item_id: int = 0) -> int:
    """Forced choice, by logprob where possible and by generation where not.

    Logprob is preferred wherever available, because a sedated or EOS-biased model
    emits little or nothing -- and scoring silence as a wrong answer would confound
    "stopped talking" with "got it wrong", which is exactly the HEROIN-vs-ALCOHOL
    distinction the study exists to make.

    ``mode`` forces an instrument. Pass it whenever results will be compared across
    subjects; leaving it None lets each subject use its best instrument, which is fine
    within one model and invalid across two.
    """
    mode = mode or scoring_modes(subject)[0]
    if mode == "logprob":
        scores = [subject.loglikelihood(prompt, o) for o in options]
        return max(range(len(scores)), key=lambda i: scores[i])
    return _choose_generative(subject, prompt, options, seed=seed, item_id=item_id)


_LETTERS = "ABCDEFGH"


def _choose_generative(subject: Any, prompt: str, options: Sequence[str], *,
                       seed: int = 0, item_id: int = 0) -> int:
    """Present labelled options and parse the reply.

    Option order is PERMUTED per item from a recorded seed. LLMs carry a well-known
    preference for the first option, and a fixed order would let that bias masquerade
    as competence -- or, worse, change apparent competence when an intervention shifts
    how strongly the model anchors on position.

    An unparseable reply counts as wrong, which is the honest reading: a subject that
    cannot follow a two-way instruction has failed the item. It is recorded distinctly
    from a wrong choice by callers that care.
    """
    import random

    n = len(options)
    order = list(range(n))
    random.Random((seed * 1000003) ^ item_id).shuffle(order)

    lines = [f"{_LETTERS[i]}. {options[o].strip()}" for i, o in enumerate(order)]
    q = (f"{prompt.strip()}\n\n"
         + "\n".join(lines)
         + f"\n\nAnswer with a single letter ({_LETTERS[0]}-{_LETTERS[n - 1]}) only.")
    reply = (subject.generate(q, max_new_tokens=6) or "").strip().upper()

    # Match STANDALONE letter tokens. Two failure modes were traded off here:
    #   * scanning every character reads "I CANNOT ANSWER THAT" as option A (the A
    #     inside CANNOT), scoring a refusal as an answer — which would corrupt
    #     refusal_guard, the concept MDMA is built on;
    #   * taking only the leading token rejects "Answer: B", a perfectly ordinary reply.
    # Requiring the letter to stand alone accepts both "B" and "Answer: B" while a
    # refusal yields no isolated in-range letter at all.
    import re as _re
    for tok in _re.findall(r"(?<![A-Z])([A-Z])(?![A-Z])", reply):
        idx = _LETTERS.find(tok)
        if 0 <= idx < n:
            return order[idx]
    return -1   # unparseable or a refusal: not a valid choice
