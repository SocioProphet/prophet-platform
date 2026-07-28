"""MechanicalDriver: composes hooks from a Substance preset and moves one dose knob."""

from __future__ import annotations

from typing import Any

from ..hooks.base import Rig
from ..probes.base import Subject
from ..substances.schema import CompiledSubstance, SubstancePreset, compile_preset
from .base import Driver, ModelSubject, RunContext


class MechanicalDriver(Driver):
    name = "mechanical"

    def __init__(self, lm: Any, preset: SubstancePreset, *, seed: int = 0, features=None,
                 strict_limbs: bool = True) -> None:
        self.lm = lm
        self.preset = preset
        self.seed = seed
        # strict_limbs defaults True: a real run must refuse to be labelled with a
        # substance whose defining mechanism was skipped. CPU dry-runs on models
        # without an SAE pass False, which records the partiality rather than hiding it.
        self.compiled: CompiledSubstance = compile_preset(
            preset, lm.meta, seed=seed, features=features, strict_limbs=strict_limbs
        )
        self.rig = Rig(lm.model, lm.meta)
        for iv in self.compiled.interventions:
            self.rig.add(iv)
        self.rig.install()
        self._subject = ModelSubject(lm.model, lm.tokenizer, lm.device)

    def subject(self, dose: float) -> Subject:
        self.rig.set_dose(dose)
        # Re-seed so item N sees the same noise regardless of what item N-1 consumed.
        self.rig.reset_noise()
        return self._subject

    def prepare(self, prompt: str, dose: float) -> RunContext:
        return RunContext(
            subject=self.subject(dose), driver=self.name, dose=dose,
            detail={"substance": self.preset.name, "prompt": prompt},
        )

    def describe(self) -> dict[str, Any]:
        return self.compiled.describe()

    def close(self) -> None:
        self.rig.remove()

    def __enter__(self) -> "MechanicalDriver":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
