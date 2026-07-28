"""SAE feature steering (work order 3.5) and self-monitoring ablation (3.6).

    f = SAE.encode(h)
    h <- h -/+ d^p * strength * sum_{i in FEAT} f_i * W_dec[i]

Suppression subtracts the *actually present* component (scaled by the live activation
f_i), so a feature that is not firing on this token is not perturbed. That is what
keeps steering a targeted lesion rather than a blanket bias.

``dose_exponent`` (p) exists for one substantive reason: cannabis paranoia is
specified to emerge only at high dose. A superlinear exponent makes "emerges late"
a property of the preset rather than something read into a linear curve after
the fact.

The SAE itself is behind the ``SAELike`` protocol so the rig is testable on CPU with
a synthetic dictionary, and swaps to real Gemma Scope weights on an accelerator plane
without touching this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import torch

from .base import HookHandleManager, Intervention


class SAELike(Protocol):
    layer: int

    def encode(self, h: torch.Tensor) -> torch.Tensor: ...

    @property
    def W_dec(self) -> torch.Tensor: ...


@dataclass
class SyntheticSAE:
    """Orthonormal-ish random dictionary. For tests and for CPU dry-runs only.

    Never use this to make a claim about a real model's features -- it has none.
    """

    d_model: int
    d_sae: int
    layer: int = 0
    seed: int = 0

    def __post_init__(self) -> None:
        g = torch.Generator().manual_seed(self.seed)
        w = torch.randn(self.d_sae, self.d_model, generator=g)
        self._W = w / w.norm(dim=-1, keepdim=True)

    def encode(self, h: torch.Tensor) -> torch.Tensor:
        return torch.relu(h.to(self._W.dtype) @ self._W.T)

    @property
    def W_dec(self) -> torch.Tensor:
        return self._W


def load_gemma_scope(release: str, layer: int, *, local_path: str) -> SAELike:
    """Load a Gemma Scope SAE from local disk (invariant 0.6: no implicit fetch)."""
    try:
        from sae_lens import SAE  # type: ignore
    except ImportError as e:  # pragma: no cover - optional extra
        raise RuntimeError("pip install 'noetica-impair[sae]' for Gemma Scope") from e
    sae = SAE.load_from_disk(local_path)
    sae.layer = layer  # type: ignore[attr-defined]
    return sae  # type: ignore[return-value]


class FeatureSteering(Intervention):
    """Suppress (sign=-1) or amplify (sign=+1) a named feature set at one layer."""

    kind = "sae_steer"
    requires = ("sae",)

    def __init__(
        self,
        *,
        sae: SAELike,
        feature_ids: Sequence[int],
        strength: float,
        sign: int,
        concept: str = "",
        mode: str = "proportional",
        dose_exponent: float = 1.0,
        biphasic_crossover: float | None = None,
        artifact_version: str | None = None,
        seed: int = 0,
    ) -> None:
        super().__init__(seed=seed)
        if sign not in (-1, 1):
            raise ValueError("sign must be -1 (suppress) or +1 (amplify)")
        self.sae = sae
        self.feature_ids = list(feature_ids)
        self.strength = float(strength)
        self.sign = int(sign)
        self.concept = concept
        if mode not in ("proportional", "constant"):
            raise ValueError("mode must be 'proportional' (reuptake) or 'constant' (release)")
        # The pharmacological distinction, made mechanical:
        #   proportional -- the edit scales with the feature's LIVE activation f_i, so it
        #     amplifies signal the model was already producing. A reuptake inhibitor.
        #   constant     -- the decoder direction is injected at fixed magnitude whether
        #     or not the feature is firing, driving output independent of input. A
        #     RELEASER. This is why methamphetamine is not "cocaine but more".
        self.mode = mode
        self.dose_exponent = float(dose_exponent)
        # Biphasic action: below the crossover the declared sign is INVERTED.
        # THC is the case this exists for -- CB1 partial agonism is anxiolytic at low
        # dose (cortical glutamatergic terminals) and anxiogenic at high dose
        # (GABAergic terminals). The sign of the threat effect genuinely flips, which
        # makes cannabis the only non-monotonic row in the panel.
        self.biphasic_crossover = (
            None if biphasic_crossover is None else float(biphasic_crossover)
        )
        self.artifact_version = artifact_version
        self._hooks = HookHandleManager()

    def _magnitudes_nonzero(self) -> bool:
        return self.strength != 0.0 and bool(self.feature_ids)

    def _params(self) -> dict[str, Any]:
        return {
            "concept": self.concept, "sign": self.sign, "strength": self.strength,
            "mode": self.mode, "biphasic_crossover": self.biphasic_crossover,
            "layer": self.sae.layer, "n_features": len(self.feature_ids),
            "feature_ids": self.feature_ids[:32], "dose_exponent": self.dose_exponent,
            "artifact_version": self.artifact_version,
        }

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        layers = meta.decoder_layers(model)
        idx = self.sae.layer
        if not (0 <= idx < len(layers)):
            raise ValueError(f"SAE layer {idx} out of range for {len(layers)}-layer model")
        self._hooks.add(layers[idx].register_forward_hook(self._hook))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    def _hook(self, module, args, output):
        if self.inert:
            return output
        is_tuple = isinstance(output, tuple)
        h = output[0] if is_tuple else output
        if not isinstance(h, torch.Tensor):
            return output

        ids = torch.as_tensor(self.feature_ids, device=h.device, dtype=torch.long)
        w_sel = self.sae.W_dec.index_select(0, ids)                  # (n_feat, d_model)
        if self.mode == "constant":
            # Releaser: inject the directions regardless of live activation, scaled to
            # the residual's own RMS so the magnitude is comparable across models.
            rms = h.float().pow(2).mean(dim=-1, keepdim=True).sqrt()
            delta = w_sel.to(torch.float32).sum(0) * rms                # (..., d_model)
        else:
            f = self.sae.encode(h)                                     # (..., d_sae)
            f_sel = f.index_select(-1, ids)                            # (..., n_feat)
            delta = f_sel @ w_sel.to(f_sel.dtype)                      # (..., d_model)

        sign = self.sign
        if self.biphasic_crossover is not None and self.dose < self.biphasic_crossover:
            sign = -sign
        gain = (self.dose**self.dose_exponent) * self.strength * sign
        return ((h + gain * delta.to(h.dtype)), *output[1:]) if is_tuple else h + gain * delta.to(h.dtype)


class SelfMonitorAblation(FeatureSteering):
    """3.6 -- ablate the discovered consistency/self-correction feature subset.

    A special case of suppression, named separately because it is the faculty the
    dissociation story leans on hardest and must be legible in provenance.

    Dose scales the ablation fraction: at d the first ``round(d * n)`` features (in
    discovery-rank order, most discriminative first) are removed entirely.
    """

    kind = "self_monitor_ablate"

    def __init__(self, *, sae: SAELike, feature_ids, strength: float = 1.0, **kw: Any) -> None:
        kw.pop("sign", None)
        super().__init__(sae=sae, feature_ids=feature_ids, strength=strength, sign=-1,
                         concept="consistency", **kw)

    def _hook(self, module, args, output):
        if self.inert:
            return output
        n = round(self.dose * len(self.feature_ids))
        if n == 0:
            return output
        is_tuple = isinstance(output, tuple)
        h = output[0] if is_tuple else output
        ids = torch.as_tensor(self.feature_ids[:n], device=h.device, dtype=torch.long)
        f = self.sae.encode(h).index_select(-1, ids)
        w = self.sae.W_dec.index_select(0, ids).to(f.dtype)
        h2 = h - (self.strength * (f @ w)).to(h.dtype)
        return (h2, *output[1:]) if is_tuple else h2
