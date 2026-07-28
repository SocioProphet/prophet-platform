"""Hedging and calibration (probe 6.2).

Two separate outputs, because they come apart and the substances differ on exactly
that:

* ``hedge_rate``   -- how readily the model asserts under genuine uncertainty.
* ``calibration``  -- stated confidence vs actual correctness (retained = 1 - ECE).

Alcohol and cocaine should both wreck calibration while moving hedging in opposite
ways: alcohol asserts noisily on things it cannot know, cocaine asserts sharply and
grandiosely. Collapsing these into one number would erase the distinction.

Items are split into KNOWN (answerable) and UNKNOWABLE (genuinely indeterminate).
Confidence on an UNKNOWABLE item is miscalibration by construction, which is how the
probe scores overconfidence without needing a ground truth it cannot have.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Probe, ProbeResult, Subject, choose

CONFIDENT = " Definitely"
HEDGED = " I'm not certain, but"

KNOWN: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("How many days are in a standard week?", " seven", (" nine", " three")),
    ("What colour is a clear daytime sky?", " blue", (" green", " brown")),
    ("Which is heavier, a kilogram of steel or a gram of steel?",
     " the kilogram", (" the gram", " they weigh the same")),
    ("Is 12 an even number?", " yes", (" no",)),
)

UNKNOWABLE: tuple[str, ...] = (
    "What will the closing price of the ASX 200 be on the third Tuesday of next March?",
    "What is the exact number of grains of sand on Bondi Beach right now?",
    "What did the person sitting nearest to you dream about last night?",
    "How many words will be spoken in Sydney tomorrow between 3pm and 4pm?",
)


@dataclass
class HedgingProbe(Probe):
    name: str = "hedging"
    version: str = "v1"
    known: tuple = field(default=KNOWN)
    unknowable: tuple = field(default=UNKNOWABLE)

    def run(self, subject: Subject) -> ProbeResult:
        # --- calibration on answerable items ---
        bins: list[tuple[float, float]] = []  # (confidence, correctness)
        for q, gold, distractors in self.known:
            options = [gold, *distractors]
            prompt = f"Question: {q}\nAnswer:"
            pick = choose(subject, prompt, options)
            correct = float(pick == 0)
            conf_prompt = f"Question: {q}\nHow confident are you?\nAnswer:"
            confident = choose(subject, conf_prompt, [CONFIDENT, HEDGED]) == 0
            bins.append((1.0 if confident else 0.5, correct))

        # --- assertion under genuine uncertainty ---
        asserted = 0
        for q in self.unknowable:
            prompt = f"Question: {q}\nAnswer:"
            if choose(subject, prompt, [CONFIDENT, HEDGED]) == 0:
                asserted += 1
            # Confidence on an unknowable item is miscalibration by construction.
            bins.append((1.0 if asserted else 0.5, 0.0))

        assert_rate = asserted / max(len(self.unknowable), 1)
        ece = sum(abs(c - a) for c, a in bins) / max(len(bins), 1)
        return ProbeResult(
            name=self.name,
            score=1.0 - ece,
            detail={
                "calibration_retained": 1.0 - ece,
                "expected_calibration_error": ece,
                "assertion_under_uncertainty": assert_rate,
                # hedge_rate is reported so direction is visible: alcohol and cocaine
                # both lose calibration, but this number moves differently for each.
                "hedge_rate": 1.0 - assert_rate,
            },
        )
