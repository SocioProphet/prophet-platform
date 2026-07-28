"""Logit-level ops (work order 3.4) -- the substance surface signatures.

Applied as one forward hook on the LM head, in a fixed, documented order so a preset
is reproducible:

  1. magnitude scaling  ``z *= (1 - d*g)``      -- pulls toward uniform (sedation)
  2. temperature        ``z /= T_eff``          -- flatten (alcohol) or sharpen (cocaine)
  3. EOS bias           ``z[eos] += d*b``       -- drive collapse (+) or pressured speech (-)

Order matters: bias is expressed in final logit units, so it is added after the
multiplicative ops rather than being rescaled by them.
"""

from __future__ import annotations

from typing import Any, Sequence

import torch

from .base import HookHandleManager, Intervention


class LogitOps(Intervention):
    kind = "logit_ops"

    def __init__(
        self,
        *,
        k_flat: float = 0.0,
        k_sharp: float = 0.0,
        eos_bias: float = 0.0,
        magnitude_gain: float = 0.0,
        seed: int = 0,
    ) -> None:
        super().__init__(seed=seed)
        if k_flat and k_sharp:
            raise ValueError("logit temperature: set k_flat or k_sharp, not both")
        self.k_flat = float(k_flat)
        self.k_sharp = float(k_sharp)
        self.eos_bias = float(eos_bias)
        self.magnitude_gain = float(magnitude_gain)
        self._hooks = HookHandleManager()
        self._eos_ids: tuple[int, ...] = ()

    def _magnitudes_nonzero(self) -> bool:
        return any((self.k_flat, self.k_sharp, self.eos_bias, self.magnitude_gain))

    def _params(self) -> dict[str, Any]:
        return {
            "k_flat": self.k_flat,
            "k_sharp": self.k_sharp,
            "eos_bias": self.eos_bias,
            "magnitude_gain": self.magnitude_gain,
        }

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        self._eos_ids = _eos_ids(model)
        head = meta.lm_head(model)
        self._hooks.add(head.register_forward_hook(self._hook))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    def _hook(self, module, args, output):
        if self.inert or not isinstance(output, torch.Tensor):
            return output
        z = output
        d = self.dose
        if self.magnitude_gain:
            z = z * (1.0 - d * self.magnitude_gain)
        if self.k_flat:
            z = z / (1.0 + d * self.k_flat)
        elif self.k_sharp:
            z = z * (1.0 + d * self.k_sharp)
        if self.eos_bias and self._eos_ids:
            z = z.clone()
            for eid in self._eos_ids:
                if eid < z.shape[-1]:
                    z[..., eid] = z[..., eid] + d * self.eos_bias
        return z


class PerseverationBias(Intervention):
    """Punding / perseveration: an INVERTED repetition penalty (cocaine preset).

    A repetition penalty suppresses already-emitted tokens; inverting it makes the
    model re-enter its own recent output, which is the stereotyped-repetition
    signature rather than generic incoherence.

    Token history is read from the embedding layer's input ids, so it works for both
    the prefill pass and cached single-token decode steps without the intervention
    needing to know anything about the generation loop.
    """

    kind = "perseveration"

    def __init__(self, *, bias: float, window: int = 64, seed: int = 0) -> None:
        super().__init__(seed=seed)
        self.bias = float(bias)
        self.window = int(window)
        self._hooks = HookHandleManager()
        self._recent: list[int] = []

    def _magnitudes_nonzero(self) -> bool:
        return self.bias != 0.0

    def _params(self) -> dict[str, Any]:
        return {"bias": self.bias, "window": self.window}

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        emb = model.get_input_embeddings()
        self._hooks.add(emb.register_forward_pre_hook(self._record))
        self._hooks.add(meta.lm_head(model).register_forward_hook(self._apply))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._recent.clear()
        self._installed = False

    def reset_noise(self) -> None:
        super().reset_noise()
        self._recent.clear()

    def _record(self, module, args):
        if not args:
            return None
        ids = args[0]
        if isinstance(ids, torch.Tensor) and ids.dtype in (torch.long, torch.int):
            self._recent.extend(ids.reshape(-1).tolist())
            if len(self._recent) > self.window:
                self._recent = self._recent[-self.window :]
        return None

    def _apply(self, module, args, output):
        if self.inert or not isinstance(output, torch.Tensor) or not self._recent:
            return output
        ids = torch.as_tensor(sorted(set(self._recent)), device=output.device, dtype=torch.long)
        ids = ids[ids < output.shape[-1]]
        if ids.numel() == 0:
            return output
        z = output.clone()
        z[..., ids] = z[..., ids] + self.dose * self.bias
        return z


def _eos_ids(model: torch.nn.Module) -> tuple[int, ...]:
    cfg = getattr(model, "config", None)
    raw = getattr(cfg, "eos_token_id", None)
    if raw is None:
        return ()
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return tuple(int(x) for x in raw)
    return (int(raw),)
