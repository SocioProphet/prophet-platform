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
    ("A train leaves at 14:20 and the journey takes 95 minutes. "
     "You want the arrival time.",
     "What is the correct first step?",
     " convert 95 minutes into hours and minutes",
     (" subtract 95 from 1420", " add 95 to 14", " divide 1420 by 95")),
    ("You have 48 sweets to share equally among 6 children, then each child eats 2. "
     "You want how many each child has left.",
     "What is the correct first step?",
     " divide 48 by 6", (" subtract 2 from 48", " multiply 6 by 2", " add 48 and 6")),
    ("A rectangle is 7cm by 4cm. You want the length of fencing to go around it.",
     "What is the correct first step?",
     " add the two side lengths together",
     (" multiply 7 by 4", " divide 7 by 4", " subtract 4 from 7")),
    ("A shirt costs $40 and is reduced by 25%. You want the sale price.",
     "What is the correct first step?",
     " find 25% of 40", (" subtract 25 from 40", " add 25 to 40", " divide 40 by 25")),
    ("You cycle 12km at 4km per hour, then rest 30 minutes. You want the total time.",
     "What is the correct first step?",
     " divide 12 by 4", (" multiply 12 by 4", " add 12 and 30", " subtract 4 from 12")),
    ("A recipe for 4 people needs 300g of rice. You are cooking for 6.",
     "What is the correct first step?",
     " find the rice needed per person",
     (" add 300 and 6", " subtract 4 from 6", " multiply 300 by 6")),
    ("A tank holds 200 litres and leaks 8 litres per hour. You want how long until empty.",
     "What is the correct first step?",
     " divide 200 by 8", (" multiply 200 by 8", " subtract 8 from 200", " add 200 and 8")),
    ("You buy 3 books at $12 and 2 pens at $3. You want the total spend.",
     "What is the correct first step?",
     " multiply 3 by 12", (" add 3 and 2", " multiply 12 by 3 and 2", " subtract 3 from 12")),
    ("A journey is 240km and you have already driven 90km. You want the fraction remaining.",
     "What is the correct first step?",
     " subtract 90 from 240", (" divide 90 by 240", " add 240 and 90", " multiply 240 by 90")),
    ("A class of 28 splits into groups of 4, and each group needs 3 sheets. "
     "You want the total sheets.",
     "What is the correct first step?",
     " divide 28 by 4", (" multiply 28 by 3", " add 4 and 3", " subtract 4 from 28")),
    ("You save $15 a week and already have $60. You want when you reach $150.",
     "What is the correct first step?",
     " subtract 60 from 150", (" divide 150 by 15", " add 60 and 15", " multiply 15 by 60")),
    ("A wall is 6m by 3m and one tin of paint covers 4 square metres. "
     "You want the tins needed.",
     "What is the correct first step?",
     " multiply 6 by 3", (" divide 6 by 3", " add 6 and 3", " divide 4 by 6")),
    ("Two pipes fill a pool in 10 and 15 minutes alone. You want the time together.",
     "What is the correct first step?",
     " find each pipe's rate per minute",
     (" add 10 and 15", " subtract 10 from 15", " multiply 10 by 15")),
    ("A meal costs $80 and you add a 15% tip, then split it between 4 people.",
     "What is the correct first step?",
     " find 15% of 80", (" divide 80 by 4", " add 15 to 80", " multiply 80 by 4")),
    ("You read 30 pages a night from a 400-page book and have read 120.",
     "What is the correct first step?",
     " subtract 120 from 400", (" divide 400 by 30", " add 120 and 30", " multiply 30 by 120")),
    ("A car uses 6 litres per 100km and you drive 250km with 20 litres in the tank.",
     "What is the correct first step?",
     " find the fuel needed for 250km",
     (" subtract 20 from 250", " divide 20 by 6", " add 6 and 250")),
    ("A rope is 24m and you cut off 3 pieces of 5m each. You want what remains.",
     "What is the correct first step?",
     " multiply 3 by 5", (" divide 24 by 5", " subtract 3 from 24", " add 24 and 5")),
    ("A worker earns $18 an hour and works 7 hours, then pays $22 for travel.",
     "What is the correct first step?",
     " multiply 18 by 7", (" subtract 22 from 18", " divide 18 by 7", " add 7 and 22")),
    ("You mix 2 parts cement to 5 parts sand and need 42kg of mixture.",
     "What is the correct first step?",
     " add 2 and 5 to get the total parts",
     (" divide 42 by 2", " multiply 42 by 5", " subtract 2 from 5")),
    ("A film starts at 19:45 and runs 132 minutes. You want the finish time.",
     "What is the correct first step?",
     " convert 132 minutes into hours and minutes",
     (" add 132 to 19", " subtract 45 from 132", " divide 1945 by 132")),
    ("A box holds 24 tins and you have 150 tins. You want the boxes needed.",
     "What is the correct first step?",
     " divide 150 by 24", (" multiply 150 by 24", " subtract 24 from 150", " add 150 and 24")),
    ("You walk 3km east then 4km north. You want the straight-line distance home.",
     "What is the correct first step?",
     " square each of the two distances",
     (" add 3 and 4", " subtract 3 from 4", " multiply 3 by 4")),
    ("A phone costs $600 over 24 monthly payments, plus a $50 deposit.",
     "What is the correct first step?",
     " subtract 50 from 600", (" divide 600 by 50", " add 24 and 50", " multiply 600 by 24")),
    ("A garden is 20m by 15m and a path 1m wide runs around the inside edge.",
     "What is the correct first step?",
     " reduce each dimension by twice the path width",
     (" multiply 20 by 15", " add 20 and 15", " subtract 1 from 20")),
    ("You have 5 hours to travel 300km and stop 40 minutes for lunch.",
     "What is the correct first step?",
     " subtract the 40-minute stop from the 5 hours",
     (" divide 300 by 5", " add 300 and 40", " multiply 5 by 40")),
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
