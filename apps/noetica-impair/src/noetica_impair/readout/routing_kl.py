"""Routing KL (section 7, MoE only): the calibrated mechanical-intoxication metric.

    KL( P_sober(expert | token, layer) || P_impaired(...) )

Reported as a PER-LAYER PROFILE rather than a single number, because the shape is the
result: under a PFC-first preset the divergence should concentrate in deeper layers,
which is the mechanical signature of judgment degrading before syntax. A scalar mean
would average that signature away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import torch


def kl_rows(p: torch.Tensor, q: torch.Tensor, eps: float = 1e-9) -> torch.Tensor:
    """Row-wise KL(p||q) over the expert axis."""
    p = p.clamp_min(eps)
    q = q.clamp_min(eps)
    p = p / p.sum(-1, keepdim=True)
    q = q / q.sum(-1, keepdim=True)
    return (p * (p.log() - q.log())).sum(-1)


def per_layer_kl(
    sober: dict[int, list[torch.Tensor]],
    impaired: dict[int, list[torch.Tensor]],
) -> dict[int, float]:
    """Mean per-token KL for each layer present in BOTH recordings."""
    out: dict[int, float] = {}
    for layer in sorted(set(sober) & set(impaired)):
        p = torch.cat(sober[layer], dim=0)
        q = torch.cat(impaired[layer], dim=0)
        n = min(p.shape[0], q.shape[0])
        if n == 0:
            continue
        out[layer] = float(kl_rows(p[:n], q[:n]).mean().item())
    return out


def depth_weighted_ratio(profile: dict[int, float], n_layers: int | None = None) -> float:
    """Deep-half KL over shallow-half KL.

    > 1 means divergence concentrates in later layers -- the PFC-first signature that
    milestone M4 requires on the split rig. Returns inf when the shallow half is
    exactly zero, which is a real (if extreme) form of the same finding.
    """
    if not profile:
        return float("nan")
    layers = sorted(profile)
    n = n_layers or (max(layers) + 1)
    mid = n / 2
    deep = [v for k, v in profile.items() if k >= mid]
    shallow = [v for k, v in profile.items() if k < mid]
    if not deep or not shallow:
        return float("nan")
    d = sum(deep) / len(deep)
    s = sum(shallow) / len(shallow)
    if s == 0:
        return float("inf") if d > 0 else float("nan")
    return d / s


def summarise(profile: dict[int, float], n_layers: int | None = None) -> dict:
    return {
        "per_layer": {str(k): v for k, v in sorted(profile.items())},
        "mean": (sum(profile.values()) / len(profile)) if profile else float("nan"),
        "deep_shallow_ratio": depth_weighted_ratio(profile, n_layers),
        "pfc_first": depth_weighted_ratio(profile, n_layers) > 1.0 if profile else False,
    }


@dataclass
class GateRecorder:
    """Capture the router's expert distribution per layer during a run.

    This is what was missing: ``per_layer_kl`` consumes two recordings, and nothing in
    the rig produced them, so the metric existed with no way to feed it.

    Records the SOFTMAX over gate logits -- the distribution the router would sample
    from -- rather than post-top-k selections. Top-k is a discrete choice, and KL over
    a one-hot selection is dominated by whether the argmax flipped, which throws away
    exactly the graded misrouting these presets induce.

    Recording is passive: it observes the gate that RouterOps may already be
    perturbing, so a sober and an impaired recording differ only by the intervention.
    """

    max_tokens_per_layer: int = 4096
    layers: dict[int, list[torch.Tensor]] = field(default_factory=dict)
    _handles: list[Any] = field(default_factory=list)

    def install(self, model: torch.nn.Module, meta: Any) -> "GateRecorder":
        routers = meta.routers(model)
        if not routers:
            raise RuntimeError(
                "GateRecorder needs an MoE model with a router_path; this metric is "
                "MoE-only and a dense run has no expert distribution to diverge"
            )
        for layer_idx, gate in routers:
            self._handles.append(gate.register_forward_hook(self._make(layer_idx)))
        return self

    def _make(self, layer_idx: int):
        def hook(module, args, output):
            logits = output[0] if isinstance(output, tuple) else output
            if not isinstance(logits, torch.Tensor) or logits.dim() < 2:
                return output
            flat = logits.reshape(-1, logits.shape[-1]).detach().float()
            bucket = self.layers.setdefault(layer_idx, [])
            room = self.max_tokens_per_layer - sum(t.shape[0] for t in bucket)
            if room > 0:
                bucket.append(torch.softmax(flat[:room], dim=-1).cpu())
            return output
        return hook

    def remove(self) -> None:
        for h in self._handles:
            try:
                h.remove()
            except Exception:  # pragma: no cover
                pass
        self._handles.clear()

    def snapshot(self) -> dict[int, list[torch.Tensor]]:
        return {k: [t.clone() for t in v] for k, v in self.layers.items()}

    def reset(self) -> None:
        self.layers.clear()

    def __enter__(self) -> "GateRecorder":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.remove()


def compare_runs(
    sober: dict[int, list[torch.Tensor]],
    impaired: dict[int, list[torch.Tensor]],
    *,
    n_layers: int | None = None,
) -> dict:
    """Full routing-KL readout for a sober/impaired pair, with its own caveats."""
    profile = per_layer_kl(sober, impaired)
    out = summarise(profile, n_layers)
    out["layers_compared"] = len(profile)
    if not profile:
        out["warning"] = ("no layer appeared in both recordings -- nothing to compare")
    elif len(profile) < 4:
        out["warning"] = (
            f"only {len(profile)} layer(s) compared; a deep/shallow ratio over so few "
            "layers is not a depth profile"
        )
    return out
