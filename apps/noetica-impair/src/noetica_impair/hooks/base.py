"""Intervention ABC + rig lifecycle.

Design invariant 0.1: every intervention exposes ``set_dose(d)`` with ``d in [0,1]``
and scales all of its own magnitudes by ``d`` internally. A substance is a named
vector of intervention parameters; a global dose sweep moves every active hook
coherently because the rig broadcasts one scalar.

Design invariant 0.3/M0: at ``d == 0`` an installed intervention must be a
bit-for-bit no-op. Subclasses get this for free by honouring ``self.inert`` --
``apply``/hook bodies return their input untouched when inert. Tests assert it.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

import torch

from ..rng import SeededNoise


class DoseError(ValueError):
    pass


class Intervention(abc.ABC):
    """One mechanical lesion with a single dose knob.

    ``kind`` is the stable identifier written into provenance. ``requires`` declares
    architecture prerequisites so ``schema.validate`` can skip (not fail) presets that
    reference ops the target model cannot support -- keeping presets portable across
    dense and MoE rigs.
    """

    kind: str = "intervention"
    requires: tuple[str, ...] = ()

    def __init__(self, *, seed: int = 0) -> None:
        self._dose: float = 0.0
        self.noise = SeededNoise(seed)
        self._installed = False

    # -- dose ---------------------------------------------------------------
    @property
    def dose(self) -> float:
        return self._dose

    def set_dose(self, d: float) -> None:
        d = float(d)
        if not (0.0 <= d <= 1.0):
            raise DoseError(f"{self.kind}: dose must be in [0,1], got {d}")
        self._dose = d

    @property
    def inert(self) -> bool:
        """True when this intervention must not perturb anything."""
        return self._dose == 0.0 or not self._magnitudes_nonzero()

    def _magnitudes_nonzero(self) -> bool:
        """Override when a preset may set an op's base magnitude to zero."""
        return True

    # -- lifecycle ----------------------------------------------------------
    @abc.abstractmethod
    def install(self, model: torch.nn.Module, meta: Any) -> None: ...

    @abc.abstractmethod
    def remove(self) -> None: ...

    def reset_noise(self) -> None:
        self.noise.reset()

    def describe(self) -> dict[str, Any]:
        """Provenance payload: everything needed to reconstruct this lesion."""
        out = {"kind": self.kind, "dose": self._dose, "seed": self.noise.seed}
        out.update(self._params())
        return out

    def _params(self) -> dict[str, Any]:
        return {}

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} d={self._dose:g}>"


class HookHandleManager:
    """Owns torch hook handles so removal is total and idempotent."""

    def __init__(self) -> None:
        self._handles: list[Any] = []

    def add(self, handle: Any) -> None:
        self._handles.append(handle)

    def remove_all(self) -> None:
        for h in self._handles:
            try:
                h.remove()
            except Exception:  # pragma: no cover - torch handle already dead
                pass
        self._handles.clear()

    def __len__(self) -> int:
        return len(self._handles)


@dataclass
class Rig:
    """A model with a set of interventions installed, driven by one dose scalar.

    The rig is the unit the sober control is defined against: the *same* rig object
    at ``dose=0`` on the *same* seed, never a freshly constructed process. That is
    what makes deltas attributable to dose rather than to load-order or impl choice.
    """

    model: torch.nn.Module
    meta: Any
    interventions: list[Intervention] = field(default_factory=list)
    _installed: bool = False
    _envelope: Any = None
    _peak_dose: float = 0.0
    _step: int = 0
    _step_handle: Any = None

    def add(self, iv: Intervention) -> "Rig":
        if self._installed:
            raise RuntimeError("add interventions before install()")
        self.interventions.append(iv)
        return self

    def install(self) -> "Rig":
        if self._installed:
            return self
        for iv in self.interventions:
            iv.install(self.model, self.meta)
        self._installed = True
        return self

    def remove(self) -> None:
        for iv in self.interventions:
            iv.remove()
        self._detach_step_driver()
        self._installed = False

    def set_dose(self, d: float) -> None:
        """Set the PEAK dose. Under a non-constant envelope the effective dose at any
        step is ``peak * envelope(step)``; under the default constant envelope the two
        are the same, so existing behaviour is unchanged."""
        self._peak_dose = float(d)
        if self._envelope is None:
            for iv in self.interventions:
                iv.set_dose(d)
        else:
            self._apply_envelope()

    def set_envelope(self, envelope: Any) -> "Rig":
        """Make dose a function of forward-pass index (see hooks.envelope).

        A step driver is attached to the input embeddings so the rig advances once per
        forward pass without any intervention needing to know about the generation loop.
        """
        self._envelope = envelope
        self._step = 0
        if envelope is None:
            self._detach_step_driver()
            self.set_dose(self._peak_dose)
            return self
        self._attach_step_driver()
        self._apply_envelope()
        return self

    @property
    def step(self) -> int:
        return self._step

    def reset_steps(self) -> None:
        self._step = 0
        if self._envelope is not None:
            self._apply_envelope()

    def _apply_envelope(self) -> None:
        mult = float(self._envelope.value(self._step)) if self._envelope else 1.0
        eff = max(0.0, min(1.0, self._peak_dose * mult))
        for iv in self.interventions:
            iv.set_dose(eff)

    def _attach_step_driver(self) -> None:
        if self._step_handle is not None:
            return
        emb = self.model.get_input_embeddings()

        def pre(module, args):
            self._apply_envelope()   # dose for THIS pass, before any layer runs
            self._step += 1
            return None

        self._step_handle = emb.register_forward_pre_hook(pre)

    def _detach_step_driver(self) -> None:
        if self._step_handle is not None:
            try:
                self._step_handle.remove()
            except Exception:  # pragma: no cover
                pass
            self._step_handle = None

    def reset_noise(self) -> None:
        """Re-seed every generator. Call before each probe so item N sees the same
        noise regardless of how many tokens item N-1 happened to consume."""
        for iv in self.interventions:
            iv.reset_noise()
        self.reset_steps()

    def describe(self) -> list[dict[str, Any]]:
        return [iv.describe() for iv in self.interventions]

    def __enter__(self) -> "Rig":
        return self.install()

    def __exit__(self, *exc: Any) -> None:
        self.remove()
