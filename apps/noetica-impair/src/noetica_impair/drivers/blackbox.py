"""Black-box driver: run the identical battery against an API model.

The battery is driver-agnostic (invariant 0.2), which is exactly what makes this
possible: the same probes that measure a hooked model can measure one you can only
send prompts to. What changes is what you may CONCLUDE.

Two hard limits, enforced rather than documented:

**No dose.** There are no hooks, so ``dose`` is meaningless here. Asking for a nonzero
dose raises rather than silently returning an unmodified subject -- a run that looks
dosed and is not would quietly corrupt every comparison it entered. Conditions on a
black box are applied through the prompt (see TopicalDriver), never through weights.

**No borrowed instrument.** A black box that cannot expose logprobs must be scored by
generation. If its white-box reference were scored by logprob, the two would be
measured with different instruments and the comparison would be between instruments
rather than models. ``negotiate_with`` forces both onto the strongest SHARED mode --
normally generative, which deliberately measures the white-box reference less
precisely than it could be. That is the price of a fair comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..probes.base import Subject, common_scoring_mode, scoring_modes
from .base import Driver, RunContext


class BlackBoxError(RuntimeError):
    pass


@dataclass
class BlackBoxSubject:
    """Wraps any completion callable as a Subject.

    ``complete(prompt, max_tokens) -> str`` is the entire required surface, so this
    fits an HTTP API, a local server, or a test double without any of them knowing
    about the rig.
    """

    complete: Callable[[str, int], str]
    model_id: str
    supports_logprobs: bool = False
    #: set when the provider CAN score continuations; most cannot
    score: Callable[[str, str], float] | None = None
    calls: int = 0

    @property
    def supported_scoring_modes(self) -> tuple[str, ...]:
        return ("logprob", "generative") if (self.supports_logprobs and self.score) \
            else ("generative",)

    def generate(self, prompt: str, *, max_new_tokens: int = 64) -> str:
        self.calls += 1
        return self.complete(prompt, max_new_tokens)

    def loglikelihood(self, prompt: str, continuation: str) -> float:
        if self.score is None:
            raise BlackBoxError(
                f"{self.model_id} does not expose logprobs. Score this pair with "
                "mode='generative' on BOTH subjects -- silently falling back on one "
                "side only would compare instruments, not models."
            )
        self.calls += 1
        return self.score(prompt, continuation)


@dataclass
class BlackBoxDriver(Driver):
    """A driver with no weights, no hooks and therefore no dose."""

    name: str = "blackbox"
    subject_impl: Any = None
    model_id: str = ""
    #: instrument to use; set by negotiate_with() when paired with a reference
    scoring_mode: str | None = None
    notes: list[str] = field(default_factory=list)

    def __init__(self, subject: BlackBoxSubject, *, model_id: str | None = None) -> None:
        self.subject_impl = subject
        self.model_id = model_id or subject.model_id
        self.name = "blackbox"
        self.scoring_mode = None
        self.notes = []

    def negotiate_with(self, *others: Any) -> str:
        """Pin the strongest instrument shared with every paired subject."""
        subs = [self.subject_impl, *others]
        mode = common_scoring_mode(*subs)
        self.scoring_mode = mode
        best_here = scoring_modes(self.subject_impl)[0]
        for o in others:
            best_other = scoring_modes(o)[0]
            if best_other != mode:
                self.notes.append(
                    f"reference downgraded from {best_other!r} to {mode!r} to match "
                    f"{self.model_id}; the reference is being measured less precisely "
                    "than it could be, on purpose"
                )
        if best_here != mode:
            self.notes.append(f"{self.model_id} downgraded {best_here!r} -> {mode!r}")
        return mode

    def subject(self, dose: float) -> Subject:
        if dose != 0.0:
            raise BlackBoxError(
                f"cannot apply dose {dose} to {self.model_id}: a black box has no "
                "hooks. Mechanical dose requires local weight access. Apply conditions "
                "through the prompt (TopicalDriver) and locate the result on a "
                "white-box ladder via readout.invariance."
            )
        return self.subject_impl

    def prepare(self, prompt: str, dose: float) -> RunContext:
        return RunContext(
            subject=self.subject(dose), driver=self.name, dose=0.0,
            detail={"model_id": self.model_id, "scoring_mode": self.scoring_mode,
                    "hooks_installed": False},
        )

    def describe(self) -> dict[str, Any]:
        return {
            "driver": self.name,
            "model_id": self.model_id,
            "hooks_installed": False,
            "mechanical_dose_possible": False,
            "scoring_mode": self.scoring_mode,
            "supported_scoring_modes": list(scoring_modes(self.subject_impl)),
            "calls": getattr(self.subject_impl, "calls", None),
            "notes": list(self.notes),
        }

    def close(self) -> None:
        return None
