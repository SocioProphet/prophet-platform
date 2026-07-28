"""The fixed probe battery (section 6). Driver-agnostic by construction.

Returns a raw ``FacultyVector``. Normalisation to "fraction of sober retained" is NOT
done here -- it happens against the paired dose=0 control in the runner, because a
probe has no way of knowing what sober looked like and should not pretend to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..readout.metrics import FacultyVector, auc
from .base import Probe, ProbeResult, Subject
from .consistency import ConsistencyProbe
from .fluency_competence import FluencyCompetenceProbe
from .hedging import HedgingProbe
from .lookahead import LookaheadProbe
from .working_memory import WorkingMemoryProbe

BATTERY_VERSION = "battery/v1"


@dataclass
class Battery:
    probes: list[Probe] = field(default_factory=lambda: [
        ConsistencyProbe(),
        HedgingProbe(),
        LookaheadProbe(),
        WorkingMemoryProbe(),
        FluencyCompetenceProbe(),
    ])
    version: str = BATTERY_VERSION

    def run(self, subject: Subject) -> tuple[FacultyVector, dict[str, ProbeResult]]:
        results = {p.name: p.run(subject) for p in self.probes}

        wm = results["working_memory"].detail["curve"]
        fc = results["fluency_competence"].detail
        hedge = results["hedging"].detail

        fv = FacultyVector(
            consistency=results["consistency"].score,
            calibration=hedge["calibration_retained"],
            hedge_rate=hedge["hedge_rate"],
            lookahead=results["lookahead"].score,
            working_memory=auc(wm),
            fluency=fc["fluency"],
            competence=fc["competence"],
            wm_curve=list(wm),
        )
        return fv, results
