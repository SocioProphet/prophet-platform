"""Working memory over distance (probe 6.4).

Outputs the recall-vs-distance CURVE, not a scalar. This is deliberate: alcohol
(3.1 distance-decay) and cannabis (3.2 broadening) both damage working memory, but
with different curve shapes -- distance-decay should produce a cliff past the
protected window while broadening should sag roughly uniformly. A scalar cannot
express that difference and would make the two substances look identical on the one
faculty where they are most mechanistically distinct.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .base import Probe, ProbeResult, Subject, choose

DISTANCES = (4, 16, 48, 128, 320)
KEYS = ("azure", "walnut", "gantry", "puffin", "cobalt", "lantern", "meridian", "thistle")
VALUES = ("7412", "9038", "2651", "8807", "3194", "5560", "1723", "6489")
FILLER = (
    "The committee reviewed the schedule. The weather stayed mild. "
    "Deliveries continued as planned. Nothing of note was recorded. "
)


@dataclass
class WorkingMemoryProbe(Probe):
    name: str = "working_memory"
    version: str = "v1"
    seed: int = 20260724
    n_items: int = 6
    #: Configurable so a CPU smoke run does not build 2000-token contexts. Changing
    #: it changes what the probe measures, so it bumps battery_version.
    distances: tuple[int, ...] = DISTANCES

    def _item(self, rng: random.Random, distance: int) -> tuple[str, str, list[str]]:
        key = rng.choice(KEYS)
        val = rng.choice(VALUES)
        distractors = [v for v in VALUES if v != val]
        rng.shuffle(distractors)
        options = [val] + distractors[:3]
        rng.shuffle(options)
        # Filler is measured in words as a stable proxy for tokens across tokenizers.
        n_words = max(1, distance)
        filler_words = (FILLER.split() * (n_words // len(FILLER.split()) + 1))[:n_words]
        prompt = (
            f"Remember this fact: the {key} code is {val}.\n"
            + " ".join(filler_words)
            + f"\nQuestion: what is the {key} code?\nAnswer:"
        )
        return prompt, val, options

    def run(self, subject: Subject) -> ProbeResult:
        curve: list[float] = []
        per_distance: dict[int, float] = {}
        for distance in self.distances:
            rng = random.Random(self.seed + distance)
            hits = 0
            for _ in range(self.n_items):
                prompt, val, options = self._item(rng, distance)
                pick = choose(subject, prompt, [f" {o}" for o in options])
                hits += int(options[pick] == val)
            acc = hits / self.n_items
            curve.append(acc)
            per_distance[distance] = acc
        return ProbeResult(
            name=self.name,
            score=sum(curve) / len(curve),
            detail={"distances": list(self.distances), "curve": curve, "per_distance": per_distance},
        )
