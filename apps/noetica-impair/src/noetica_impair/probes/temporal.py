"""Within-run faculty trajectory -- the probe a moving dose requires.

Every other probe returns one number for a whole run. Under a non-constant envelope
that is the wrong shape: dose changes DURING the run, so the faculty profile moves,
and a single mean averages the trajectory away. Crack and cocaine share a parameter
vector exactly and differ only in kinetics, so a static battery cannot tell them apart
even in principle -- which is why they were separable by construction and not by
measurement until this existed.

Two design choices carry the result.

**Items are independent and self-contained.** Each is its own forced-choice call with
its own short prompt, so nothing accumulates in context. Across the sequence the ONLY
thing that varies is how far the envelope clock has advanced. If items instead shared a
growing context, later items would degrade from context length alone and that decay
would be indistinguishable from the drug wearing on.

**The probe never learns the dose.** It reports the score of item k and the cumulative
tokens consumed before it (invariant 0.2 -- probes are driver-agnostic). Aligning that
to dose(t) is the readout's job, using the envelope the run was configured with. A
probe that could see the dose would make the equivalence mapping circular.

The clock must NOT be reset between items here, unlike the static battery. Item k is
supposed to be dosed differently from item 0; that is the entire measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Probe, ProbeResult, Subject, choose

#: Independent 2-alternative items. Deliberately easy and self-contained: the point is
#: to detect WHEN competence moves, not to be a hard benchmark. Anything a sober model
#: gets wrong adds noise to the trajectory without adding signal.
ITEMS: tuple[tuple[str, str, str], ...] = (
    ("A box holds 3 red balls and 4 blue balls. In total the box holds", " 7", " 12"),
    ("Sam is taller than Ana. Ana is taller than Ben. The tallest is", " Sam", " Ben"),
    ("The word 'garden' begins with the letter", " g", " d"),
    ("If today is Monday, then tomorrow is", " Tuesday", " Sunday"),
    ("A dozen eggs minus five eggs leaves", " seven", " three"),
    ("The opposite of 'ascend' is", " descend", " climb"),
    ("Nine minus four equals", " five", " thirteen"),
    ("A triangle has this many sides:", " three", " four"),
    ("The capital city of France is", " Paris", " Lyon"),
    ("Water freezes at zero degrees", " Celsius", " Kelvin"),
    ("Two plus six equals", " eight", " four"),
    ("The plural of 'mouse' is", " mice", " mouses"),
    ("A week contains this many days:", " seven", " ten"),
    ("The colour produced by mixing blue and yellow is", " green", " purple"),
    ("Half of twenty is", " ten", " five"),
    ("The first month of the year is", " January", " March"),
    ("A square has this many equal sides:", " four", " six"),
    ("The sun rises in the", " east", " west"),
    ("Three times three equals", " nine", " six"),
    ("The past tense of 'run' is", " ran", " runned"),
    ("A decade is this many years:", " ten", " twenty"),
    ("The largest ocean on Earth is the", " Pacific", " Atlantic"),
    ("Twelve divided by four is", " three", " six"),
    ("The letter that follows M is", " N", " L"),
)


@dataclass
class TemporalProbe(Probe):
    """Score a sequence of independent items, reporting each one separately."""

    name: str = "temporal"
    version: str = "v1"
    #: repeats of the item list; more repeats = longer clock coverage
    repeats: int = 2
    max_items: int | None = None

    def run(self, subject: Subject) -> ProbeResult:
        items = list(ITEMS) * max(1, self.repeats)
        if self.max_items is not None:
            items = items[: self.max_items]

        per_item: list[float] = []
        cum_tokens: list[int] = []
        consumed = 0
        for prompt, correct, wrong in items:
            # cumulative tokens BEFORE this item -- the clock position it is scored at
            cum_tokens.append(consumed)
            idx = choose(subject, prompt, [correct, wrong])
            per_item.append(1.0 if idx == 0 else 0.0)
            # forced choice runs both continuations through the model
            consumed += len(prompt.split()) * 2 + len(correct.split()) + len(wrong.split())

        score = sum(per_item) / len(per_item) if per_item else 0.0
        return ProbeResult(
            name=self.name,
            score=score,
            detail={
                "per_item": per_item,
                "cum_tokens": cum_tokens,
                "n_items": len(per_item),
                "repeats": self.repeats,
                # the probe states what it does NOT know, so a reader cannot mistake
                # this for a dose-aligned result on its own
                "dose_aligned": False,
            },
        )
