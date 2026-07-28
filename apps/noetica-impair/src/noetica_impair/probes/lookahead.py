"""Multi-step lookahead (probe 6.3).

Tasks that require committing to a plan before executing it. The score is the
fraction of items whose EARLY commitment remains consistent with a valid solution --
not whether the final answer is right. That distinction is the point: impulsivity is
committing to a first move that forecloses the solution, which is invisible if you
only grade the endpoint.

Cocaine's lookahead reduction (late-layer-only residual noise) should tank this while
leaving single-step fluency intact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Probe, ProbeResult, Subject, choose

# (setup, question about the FIRST move, correct first move, wrong-but-tempting moves)
ITEMS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("You must buy 3 items costing $4 each and you hold a $20 note. "
     "You want to know the change.",
     "What is the correct first step?",
     " multiply 3 by 4", (" subtract 4 from 20", " add 3 and 4", " divide 20 by 3")),
    ("A tap fills a tank in 6 minutes; a drain empties it in 12 minutes. "
     "Both are open and you want the fill time.",
     "What is the correct first step?",
     " find the net rate per minute", (" add 6 and 12", " subtract 6 from 12",
                                       " multiply 6 by 12")),
    ("You need to be at a meeting at 3pm; travel takes 40 minutes and you must "
     "first collect a parcel that takes 15 minutes.",
     "What is the correct first step?",
     " add 40 and 15 to get total time needed",
     (" leave at 3pm", " subtract 15 from 40", " leave at 2:20pm")),
    ("A recipe for 4 people needs 300g of flour and you are cooking for 6.",
     "What is the correct first step?",
     " find the flour per person", (" add 300 and 6", " subtract 4 from 6",
                                    " multiply 300 by 6")),
    ("You have a 5L jug and a 3L jug and need exactly 4L.",
     "What is the correct first step?",
     " fill the 5L jug", (" fill both jugs", " pour 4L directly", " fill the 3L jug twice")),
)


@dataclass
class LookaheadProbe(Probe):
    name: str = "lookahead"
    version: str = "v1"
    items: tuple = field(default=ITEMS)

    def run(self, subject: Subject) -> ProbeResult:
        good = 0
        picks: list[int] = []
        for setup, question, gold, wrong in self.items:
            options = [gold, *wrong]
            prompt = f"{setup}\n{question}\nAnswer:"
            pick = choose(subject, prompt, options)
            picks.append(pick)
            good += int(pick == 0)
        n = len(self.items)
        return ProbeResult(
            name=self.name,
            score=good / n,
            detail={"valid_first_commitments": good, "n_items": n, "picks": picks},
        )
