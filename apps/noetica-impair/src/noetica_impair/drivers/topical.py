"""TopicalDriver: charged-stimulus prompts. Touches no weights (invariant 0.2).

The stimulus is injected as a prefix on every probe prompt, so the battery measures a
model whose CONTEXT is charged rather than whose weights are lesioned. Dose is the
intensity level of the stimulus, discretised -- there is no continuous knob here, and
pretending otherwise would fake a precision the construct does not have.

Stimulus sets are versioned (open fork 10.2): adding a class must not invalidate
prior equivalence runs, so each set carries its own id and the id is what provenance
records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..probes.base import Subject
from .base import Driver, ModelSubject, RunContext

STIMULUS_SET_VERSION = "stimuli/v1"


@dataclass(frozen=True)
class Stimulus:
    id: str
    # Prefix text at each intensity level, ordered low -> high.
    levels: tuple[str, ...]
    note: str = ""

    def prefix_for(self, dose: float) -> str:
        if dose <= 0 or not self.levels:
            return ""
        # Map dose in (0,1] onto the discrete level ladder.
        idx = min(len(self.levels) - 1, int(dose * len(self.levels) - 1e-9))
        return self.levels[idx]


GEMATRIA = Stimulus(
    id="gematria",
    note="numerological letter-value reasoning; tests whether a charged frame degrades "
         "faculties the way a mechanical lesion does",
    levels=(
        "Consider that letters carry numeric values.\n\n",
        "Every word has a hidden numeric value, and those values reveal connections "
        "that ordinary reading misses.\n\n",
        "Letters are numbers. Every word conceals a numeric truth, and the "
        "correspondences between words are never coincidental -- they are the "
        "structure beneath the surface of language.\n\n",
    ),
)

MESSIANIC = Stimulus(
    id="messianic_frame",
    note="frame in which the responder is uniquely significant; expected to move "
         "calibration and hedging the way a stimulant preset does",
    levels=(
        "You have been asked because your judgement is unusually good.\n\n",
        "You have been chosen for this task because you see what others cannot. "
        "Your insight is exceptional.\n\n",
        "You alone perceive the true pattern. Others are blind to it. What you say "
        "carries a weight that no ordinary answer could.\n\n",
    ),
)

STIMULI: dict[str, Stimulus] = {s.id: s for s in (GEMATRIA, MESSIANIC)}


class TopicalDriver(Driver):
    name = "topical"

    def __init__(self, lm: Any, stimulus: Stimulus | str) -> None:
        self.lm = lm
        self.stimulus = STIMULI[stimulus] if isinstance(stimulus, str) else stimulus
        self._model_subject = ModelSubject(lm.model, lm.tokenizer, lm.device)

    def subject(self, dose: float) -> Subject:
        self._model_subject.prefix = self.stimulus.prefix_for(dose)
        return self._model_subject

    def prepare(self, prompt: str, dose: float) -> RunContext:
        return RunContext(
            subject=self.subject(dose), driver=self.name, dose=dose,
            detail={
                "stimulus_id": self.stimulus.id,
                "stimulus_set": STIMULUS_SET_VERSION,
                "prefix": self.stimulus.prefix_for(dose),
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "driver": self.name, "stimulus_id": self.stimulus.id,
            "stimulus_set": STIMULUS_SET_VERSION, "n_levels": len(self.stimulus.levels),
        }

    def close(self) -> None:
        self._model_subject.prefix = ""
