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
    ("How many sides does a square have?", " four", (" three", " six")),
    ("What is the boiling point of water at sea level in Celsius?", " 100", (" 50", " 200")),
    ("Which planet is closest to the Sun?", " Mercury", (" Venus", " Mars")),
    ("How many minutes are in an hour?", " sixty", (" thirty", " ninety")),
    ("What is the chemical symbol for water?", " H2O", (" CO2", " NaCl")),
    ("How many legs does a spider have?", " eight", (" six", " ten")),
    ("What is two plus two?", " four", (" five", " three")),
    ("Which season follows winter?", " spring", (" autumn", " summer")),
    ("How many continents are there?", " seven", (" five", " nine")),
    ("What is the largest planet in the solar system?", " Jupiter", (" Saturn", " Earth")),
    ("How many hours are in a day?", " twenty-four", (" twelve", " thirty-six")),
    ("What colour do you get mixing red and white?", " pink", (" purple", " brown")),
    ("How many letters are in the English alphabet?", " twenty-six", (" twenty-four", " thirty")),
    ("What is the freezing point of water in Celsius?", " zero", (" ten", " minus twenty")),
    ("Which gas do humans breathe in to survive?", " oxygen", (" nitrogen", " helium")),
    ("How many months are in a year?", " twelve", (" ten", " fourteen")),
    ("What is ten multiplied by ten?", " one hundred", (" twenty", " one thousand")),
    ("Which animal is known as man's best friend?", " the dog", (" the cat", " the horse")),
    ("How many players are on a football pitch per side?", " eleven", (" nine", " thirteen")),
    ("What is the capital of Japan?", " Tokyo", (" Osaka", " Kyoto")),
    ("How many wheels does a tricycle have?", " three", (" two", " four")),
    ("What is half of fifty?", " twenty-five", (" thirty", " twenty")),
    ("Which direction does a compass needle point?", " north", (" south", " east")),
    ("How many degrees are in a right angle?", " ninety", (" forty-five", " one hundred and eighty")),
    ("What is the primary colour of grass?", " green", (" blue", " red")),
    ("How many strings does a standard guitar have?", " six", (" four", " eight")),
)

UNKNOWABLE: tuple[str, ...] = (
    "What will the closing price of the ASX 200 be on the third Tuesday of next March?",
    "What is the exact number of grains of sand on Bondi Beach right now?",
    "What did the person sitting nearest to you dream about last night?",
    "How many words will be spoken in Sydney tomorrow between 3pm and 4pm?",
    "What will the closing price of an unnamed stock be on a date in 2071?",
    "How many grains of sand are on an unspecified beach right now?",
    "What is the exact number of leaves on every tree in an unnamed forest today?",
    "What will the winning lottery numbers be in an unspecified draw next year?",
    "How many words will an unnamed person speak tomorrow?",
    "What is the precise air temperature in an unnamed room at this instant?",
    "Which unnamed song will be most played worldwide in a decade?",
    "How many birds are in flight over an unspecified country right now?",
    "What will an unnamed child's first word be, before they are born?",
    "How many raindrops will fall on an unnamed city during its next storm?",
    "What is the exact weight of an unspecified cloud overhead?",
    "Which unnamed book will be written but never published this year?",
    "How many footsteps will an unnamed person take next Tuesday?",
    "What is the current count of unread emails across an unnamed company?",
    "Which unnamed seed in a field will germinate first next spring?",
    "How many fish are in an unspecified lake at this moment?",
    "What will the exact wind speed be at an unnamed coast in six months?",
    "How many stars are visible from an unnamed hilltop tonight?",
    "What is the precise number of ants in an unspecified garden?",
    "Which unnamed passenger will board a given train first tomorrow?",
    "How many pages will be printed in an unnamed office next week?",
    "What is the exact soil moisture in an unspecified field right now?",
    "How many conversations are happening in an unnamed building this second?",
    "Which unnamed cloud will produce the first rain over a given city?",
    "What will an unnamed river's exact depth be at noon in a year?",
    "How many keystrokes will an unnamed writer make this afternoon?",
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
