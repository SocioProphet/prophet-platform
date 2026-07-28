"""Feed-forward (prior) attenuation -- the psychedelic mechanism.

The transformer decoder layer is ``h = h + attn(h)`` then ``h = h + mlp(h)``. Those two
branches do different jobs: attention integrates the CONTEXT in front of the model,
while the MLP is where learned, context-independent knowledge lives (the
key-value-memory reading of feed-forward layers). Scaling the MLP branch down
therefore shifts the balance from *what the model knows* toward *what it is currently
being shown*.

That is a mechanical statement of the REBUS account of psychedelics -- relaxed
high-level priors, with incoming data weighted more heavily than the model's
expectations. Gating it to later layers matters: early-layer feed-forward carries
lexical and syntactic regularities you want preserved (fluency must hold), while
later-layer feed-forward carries the abstract priors you want relaxed.

This is a genuinely different axis from everything else in the rig. Residual noise
CORRUPTS a computation; attention ops change WHAT IS ATTENDED TO; this changes the
RATIO between two intact computations, and it is monotone and noise-free -- so a
result under it cannot be explained away as "you just added noise until it broke".
"""

from __future__ import annotations

from typing import Any

import torch

from .base import HookHandleManager, Intervention


class MLPAttenuation(Intervention):
    """Scale the feed-forward branch: ``mlp_out *= (1 - d * strength * depth_gate)``.

    ``strength`` of 1.0 at full dose removes the branch entirely at the deepest layer.
    ``min_layer_frac`` protects early layers so surface fluency survives.
    """

    kind = "mlp_attenuation"

    def __init__(
        self,
        *,
        strength: float,
        min_layer_frac: float = 0.5,
        depth_scaled: bool = True,
        seed: int = 0,
    ) -> None:
        super().__init__(seed=seed)
        self.strength = float(strength)
        self.min_layer_frac = float(min_layer_frac)
        self.depth_scaled = bool(depth_scaled)
        self._hooks = HookHandleManager()
        self._n_layers = 0

    def _magnitudes_nonzero(self) -> bool:
        return self.strength != 0.0

    def _params(self) -> dict[str, Any]:
        return {
            "strength": self.strength,
            "min_layer_frac": self.min_layer_frac,
            "depth_scaled": self.depth_scaled,
        }

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        layers = meta.decoder_layers(model)
        self._n_layers = len(layers)
        for idx, layer in enumerate(layers):
            mlp = getattr(layer, "mlp", None) or getattr(layer, "feed_forward", None)
            if mlp is None:
                continue
            self._hooks.add(mlp.register_forward_hook(self._make(idx)))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    def _make(self, layer_idx: int):
        def hook(module, args, output):
            if self.inert:
                return output
            frac = (layer_idx + 1) / max(self._n_layers, 1)
            if frac < self.min_layer_frac:
                return output
            gate = frac if self.depth_scaled else 1.0
            factor = 1.0 - self.dose * self.strength * gate
            if isinstance(output, tuple):
                return (output[0] * factor, *output[1:])
            return output * factor if isinstance(output, torch.Tensor) else output

        return hook
