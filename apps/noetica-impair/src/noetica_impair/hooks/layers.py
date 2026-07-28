"""Layer bypass -- the dissociative mechanism.

A decoder layer computes an update and adds it to the residual stream. This
intervention discards that update: ``h_out <- (1-p)*h_out + p*h_in``. The information
still flows through the model, but a stage of integration simply did not happen.

That is a different lesion from residual noise, and the difference is the point.
Noise CORRUPTS a computation -- the layer still runs, its output is just degraded.
Bypass DISCONNECTS one -- the layer's contribution is absent while every other layer
is perfectly intact. Behaviourally the expected signature is derailment rather than
error: locally well-formed continuations that fail to stay bound to what came before,
because the stages that would have bound them were skipped.

Gated to a mid/late band by default. Bypassing early layers destroys token-level
competence and would show up as a coarse lesion rather than a dissociation.
"""

from __future__ import annotations

from typing import Any

import torch

from .base import HookHandleManager, Intervention


class LayerBypass(Intervention):
    """Drop a fraction of each in-scope layer's update.

    ``fraction`` is the blend weight toward the layer's own input at full dose, so
    dose scales how much of the layer's contribution goes missing.
    """

    kind = "layer_bypass"

    def __init__(
        self,
        *,
        fraction: float,
        min_layer_frac: float = 0.4,
        max_layer_frac: float = 0.95,
        seed: int = 0,
    ) -> None:
        super().__init__(seed=seed)
        self.fraction = float(fraction)
        self.min_layer_frac = float(min_layer_frac)
        self.max_layer_frac = float(max_layer_frac)
        self._hooks = HookHandleManager()
        self._n_layers = 0

    def _magnitudes_nonzero(self) -> bool:
        return self.fraction != 0.0

    def _params(self) -> dict[str, Any]:
        return {
            "fraction": self.fraction,
            "min_layer_frac": self.min_layer_frac,
            "max_layer_frac": self.max_layer_frac,
        }

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        layers = meta.decoder_layers(model)
        self._n_layers = len(layers)
        for idx, layer in enumerate(layers):
            self._hooks.add(layer.register_forward_hook(self._make(idx)))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    def _make(self, layer_idx: int):
        def hook(module, args, output):
            if self.inert:
                return output
            frac = (layer_idx + 1) / max(self._n_layers, 1)
            if not (self.min_layer_frac <= frac <= self.max_layer_frac):
                return output
            h_in = args[0] if args else None
            if not isinstance(h_in, torch.Tensor):
                return output
            is_tuple = isinstance(output, tuple)
            h_out = output[0] if is_tuple else output
            if not isinstance(h_out, torch.Tensor) or h_out.shape != h_in.shape:
                return output
            p = self.dose * self.fraction
            blended = (1.0 - p) * h_out + p * h_in
            return (blended, *output[1:]) if is_tuple else blended

        return hook
