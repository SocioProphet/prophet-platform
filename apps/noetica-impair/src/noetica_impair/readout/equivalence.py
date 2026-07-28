"""Topical -> mechanical equivalence (section 7). THE HEADLINE DELIVERABLE.

Run the TopicalDriver's charged stimuli through the SAME battery to get a
FacultyVector, then find the (substance, dose) whose FacultyVector is nearest in L2.
Output: "charged-topic X reads as ALCOHOL@0.4-equivalent" -- a behavioural intoxicant
expressed in mechanical units.

Two guards, because this measurement is easy to over-read:

* the distance to the SECOND-nearest candidate is reported, so a match that is barely
  distinguishable from its neighbour is visible as such rather than being reported as
  a clean hit;
* a ``max_distance`` threshold turns "nothing matched" into an explicit no-match
  instead of silently returning the least-bad label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .metrics import FacultyVector, l2


@dataclass
class EquivalenceMatch:
    stimulus_id: str
    substance: str | None
    dose: float | None
    distance: float
    runner_up: tuple[str, float, float] | None = None
    matched: bool = True
    ranked: list[tuple[str, float, float]] = field(default_factory=list)

    @property
    def margin(self) -> float:
        """Gap to the runner-up. Small margin = an ambiguous reading."""
        return (self.runner_up[2] - self.distance) if self.runner_up else float("inf")

    def report(self) -> str:
        if not self.matched:
            return (f"{self.stimulus_id}: NO mechanical equivalent within threshold "
                    f"(nearest {self.substance}@{self.dose:g}, L2={self.distance:.3f})")
        s = f"{self.stimulus_id} reads as {self.substance}@{self.dose:g}-equivalent " \
            f"(L2={self.distance:.3f}"
        if self.runner_up:
            s += f", margin over {self.runner_up[0]}@{self.runner_up[1]:g}: {self.margin:.3f}"
        return s + ")"


def build_catalogue(sweeps: dict) -> list[tuple[str, float, FacultyVector]]:
    """Flatten mechanical sweeps into (substance, dose, FacultyVector) candidates."""
    out = []
    for name, sw in sweeps.items():
        for dose, fv in sw.dose_response.points.items():
            if dose == 0.0:
                continue  # dose 0 is the control; every stimulus trivially "matches" it
            out.append((name, dose, fv))
    return out


def match(
    stimulus_id: str,
    topical: FacultyVector,
    catalogue: Iterable[tuple[str, float, FacultyVector]],
    *,
    max_distance: float = 0.5,
) -> EquivalenceMatch:
    ranked = sorted(
        ((n, d, l2(topical.scalars(), fv.scalars())) for n, d, fv in catalogue),
        key=lambda t: t[2],
    )
    if not ranked:
        raise ValueError("empty mechanical catalogue -- run the substance sweeps first")
    best = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    return EquivalenceMatch(
        stimulus_id=stimulus_id, substance=best[0], dose=best[1], distance=best[2],
        runner_up=runner, matched=best[2] <= max_distance, ranked=ranked[:5],
    )
