"""Depth-scaled residual noise (work order 3.3) -- the PFC-first backbone.

``scale = d * sigma * (L / n_layers)``; ``h += N(0, (scale * ||h||_rms)^2)``.

Later layers take proportionally more noise, so abstract/executive computation
degrades before early-layer syntax. This is the mechanism behind "judgment before
grammar" and it is what makes the fluency-vs-competence split (probe 6.5) read.

Noise is scaled by the per-token RMS of the residual, not a fixed absolute, so the
same sigma means the same relative perturbation across models and layer widths.
"""

from __future__ import annotations

from typing import Any

import torch

from .base import HookHandleManager, Intervention


class DepthScaledResidualNoise(Intervention):
    kind = "residual_noise"

    def __init__(self, *, sigma: float, seed: int = 0, min_layer_frac: float = 0.0) -> None:
        super().__init__(seed=seed)
        self.sigma = float(sigma)
        self.min_layer_frac = float(min_layer_frac)
        self._hooks = HookHandleManager()
        self._n_layers = 0

    def _magnitudes_nonzero(self) -> bool:
        return self.sigma != 0.0

    def _params(self) -> dict[str, Any]:
        return {"sigma": self.sigma, "min_layer_frac": self.min_layer_frac}

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        layers = meta.decoder_layers(model)
        self._n_layers = len(layers)
        for idx, layer in enumerate(layers):
            self._hooks.add(layer.register_forward_hook(self._make_hook(idx)))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    def _make_hook(self, layer_idx: int):
        def hook(module, args, output):
            if self.inert:
                return output
            frac = (layer_idx + 1) / max(self._n_layers, 1)
            if frac < self.min_layer_frac:
                return output
            # Decoder layers return a Tensor in transformers>=5, a tuple in <5.
            is_tuple = isinstance(output, tuple)
            h = output[0] if is_tuple else output
            if not isinstance(h, torch.Tensor):
                return output
            scale = self.dose * self.sigma * frac
            rms = h.float().pow(2).mean(dim=-1, keepdim=True).sqrt().to(h.dtype)
            h = h + self.noise.randn_like(h) * (scale * rms)
            return (h, *output[1:]) if is_tuple else h

        return hook
