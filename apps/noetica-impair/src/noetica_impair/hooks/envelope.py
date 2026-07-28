"""Dose as a function of time -- the pharmacokinetic axis.

Everything else in this rig treats dose as a scalar held constant for a run. That is
enough to separate substances whose *parameter vectors* differ, and useless for
substances whose parameter vectors are identical and whose difference is entirely in
the time course.

Crack is exactly that case. Smoked cocaine is not a different drug from cocaine at the
receptor -- same reuptake inhibition, same parameter vector. What differs is
kinetics: near-immediate onset, a short peak, a steep decay, and a crash that
undershoots baseline. If CRACK were added as another entry in ``presets.py`` with
slightly larger magnitudes, it would be COCAINE with a bigger number, and the
dissociation matrix would correctly report the two as one lesion with two labels.

So the honest way to add crack is to add an axis, not a preset: dose becomes
``peak * envelope(step)``, and the rig advances ``step`` once per forward pass.

Note the consequence for measurement. A run under a non-constant envelope is no
longer summarised by a single FacultyVector -- the whole claim is that the faculty
profile MOVES during the run. Reading such a run with the current static battery would
average the trajectory away and report a muddle. That probe does not exist yet, and is
named in the README rather than faked here.
"""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from typing import Any


class DoseEnvelope(abc.ABC):
    """Maps a step index to a dose multiplier in [0, 1]."""

    kind: str = "envelope"

    @abc.abstractmethod
    def value(self, step: int) -> float: ...

    def describe(self) -> dict[str, Any]:
        return {"envelope": self.kind}

    def trace(self, n: int) -> list[float]:
        """The full multiplier curve -- logged so a run's exposure is auditable."""
        return [self.value(i) for i in range(n)]


@dataclass
class Constant(DoseEnvelope):
    """The default. Every existing preset uses this implicitly."""

    kind: str = "constant"

    def value(self, step: int) -> float:
        return 1.0


@dataclass
class Bolus(DoseEnvelope):
    """Rise, plateau, exponential decay, and an optional undershoot.

    ``rebound`` is the crash: after the drug clears, the multiplier goes NEGATIVE-ward
    toward a floor below baseline. Since dose is clamped at 0, a rebound is expressed
    as a return to 0 that then *stays* there for the rest of the run -- the rig cannot
    represent "worse than sober" as a dose, and pretending otherwise would be a lie
    about what the knob does. A true crash needs an opposing preset, which is noted in
    the README as an open question rather than smuggled in here.
    """

    onset: int = 4          # steps to reach peak
    plateau: int = 12       # steps held at peak
    half_life: int = 24     # steps for the decay to halve
    rebound: float = 0.0    # 0..1, how far below peak the post-decay floor sits
    kind: str = "bolus"

    def value(self, step: int) -> float:
        if step < 0:
            return 0.0
        if step < self.onset:
            return (step + 1) / max(self.onset, 1)
        held = step - self.onset
        if held < self.plateau:
            return 1.0
        decayed = held - self.plateau
        v = 0.5 ** (decayed / max(self.half_life, 1))
        floor = 0.0
        return max(floor, v * (1.0 - self.rebound) + floor)

    def describe(self) -> dict[str, Any]:
        return {
            "envelope": self.kind, "onset": self.onset, "plateau": self.plateau,
            "half_life": self.half_life, "rebound": self.rebound,
        }


#: Insufflated/oral cocaine: slow to arrive, long plateau, gentle offset.
COCAINE_KINETICS = Bolus(onset=24, plateau=96, half_life=120, rebound=0.0)

#: Smoked cocaine: near-instant, brief, steep. Same receptor, different curve --
#: this is the ONLY thing that distinguishes CRACK from COCAINE in this rig.
CRACK_KINETICS = Bolus(onset=2, plateau=8, half_life=14, rebound=0.35)

#: Psilocybin vs LSD differ mainly in duration; see presets.py for why that is a
#: weak basis for a dissociation claim.
LSD_KINETICS = Bolus(onset=32, plateau=256, half_life=256, rebound=0.0)
PSILOCYBIN_KINETICS = Bolus(onset=16, plateau=96, half_life=96, rebound=0.0)


#: Methamphetamine: slower to arrive than smoked cocaine, and then it simply stays.
#: The long plateau is the point -- sustained exposure is where stereotypy and
#: paranoia emerge, and it is the opposite end of the same axis as CRACK.
METH_KINETICS = Bolus(onset=12, plateau=512, half_life=384, rebound=0.25)


ENVELOPES: dict[str, DoseEnvelope] = {
    "constant": Constant(),
    "cocaine": COCAINE_KINETICS,
    "crack": CRACK_KINETICS,
    "lsd": LSD_KINETICS,
    "psilocybin": PSILOCYBIN_KINETICS,
    "meth": METH_KINETICS,
}


def get(name: str) -> DoseEnvelope:
    if name not in ENVELOPES:
        raise KeyError(f"unknown envelope {name!r}; known: {sorted(ENVELOPES)}")
    return ENVELOPES[name]
