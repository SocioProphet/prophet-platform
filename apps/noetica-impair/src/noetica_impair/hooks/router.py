"""MoE router interventions (work order 3.7).

Attaches a forward hook to each *routed* gate and rewrites its output. Verified
against transformers>=5 Mixtral, whose ``MixtralTopKRouter.forward`` returns
``(router_logits, router_scores, router_indices)`` where scores are top-k
probabilities renormalised to sum to 1. Older gates (a bare ``nn.Linear`` returning
raw logits) are also supported.

Composition order is fixed and documented so a preset is reproducible:

  1. router-logit noise      g += N(0, (d*sigma_r)^2)   -> misrouting
  2. gate-entropy flatten    g /= (1 + d*k_r)           -> hedged expert mixture
  3. softmax -> probabilities
  4. anti-route              ranks k+1..2k substituted per token with prob d
  5. top-k reduction         k -> 1 above a dose threshold (capacity starvation)
  6. renormalise the surviving selection
  7. expert dropout          with prob d, zero a selected expert's contribution

Dropout comes last, after renormalisation, because the intent is lost capacity: the
token genuinely loses that expert's contribution rather than having it redistributed.

DeepSeek split rule: ``ArchMeta.routers()`` yields routed gates only, so shared
experts are structurally untouchable from here -- fluency substrate preserved while
specialised judgment degrades, which is PFC-first for free.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F

from .base import HookHandleManager, Intervention


class RouterOps(Intervention):
    kind = "router_ops"
    requires = ("moe",)

    def __init__(
        self,
        *,
        sigma_r: float = 0.0,
        k_r: float = 0.0,
        anti_route: float = 0.0,
        expert_dropout: float = 0.0,
        topk_reduce_at: float | None = None,
        seed: int = 0,
    ) -> None:
        super().__init__(seed=seed)
        self.sigma_r = float(sigma_r)
        self.k_r = float(k_r)
        self.anti_route = float(anti_route)
        self.expert_dropout = float(expert_dropout)
        self.topk_reduce_at = topk_reduce_at
        self._hooks = HookHandleManager()
        self._n_experts = 0

    def _magnitudes_nonzero(self) -> bool:
        return any((self.sigma_r, self.k_r, self.anti_route, self.expert_dropout)) or (
            self.topk_reduce_at is not None
        )

    def _params(self) -> dict[str, Any]:
        return {
            "sigma_r": self.sigma_r, "k_r": self.k_r, "anti_route": self.anti_route,
            "expert_dropout": self.expert_dropout, "topk_reduce_at": self.topk_reduce_at,
        }

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        routers = meta.routers(model)
        if not routers:
            raise RuntimeError(
                "RouterOps requires an MoE model with a router_path; none found. "
                "Presets should be filtered by substances.schema.validate first."
            )
        if meta.moe is not None:
            self._n_experts = meta.moe.n_experts
        for _, gate in routers:
            self._hooks.add(gate.register_forward_hook(self._hook))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    # -- core ---------------------------------------------------------------
    def _hook(self, module, args, output):
        if self.inert:
            return output
        if isinstance(output, tuple) and len(output) == 3:
            logits, _scores, _idx = output
            top_k = int(getattr(module, "top_k", _idx.shape[-1]))
            new_logits = self._perturb_logits(logits)
            scores, idx = self._select(new_logits, top_k)
            return (new_logits, scores.to(_scores.dtype), idx)
        if isinstance(output, torch.Tensor):
            # Bare gate linear: only the logit-space ops are expressible here; the
            # host module does its own top-k downstream.
            return self._perturb_logits(output)
        raise RuntimeError(
            f"unsupported router output {type(output)} len="
            f"{len(output) if isinstance(output, tuple) else 'n/a'}; add a case here "
            "rather than silently passing it through"
        )

    def _perturb_logits(self, g: torch.Tensor) -> torch.Tensor:
        d = self.dose
        if self.sigma_r:
            g = g + self.noise.randn_like(g) * (d * self.sigma_r)
        if self.k_r:
            g = g / (1.0 + d * self.k_r)
        return g

    def _select(self, logits: torch.Tensor, top_k: int) -> tuple[torch.Tensor, torch.Tensor]:
        d = self.dose
        probs = F.softmax(logits.float(), dim=-1)
        n_exp = probs.shape[-1]
        T = probs.shape[0]
        dev = probs.device

        want = min(2 * top_k, n_exp)
        vals, idx = torch.topk(probs, want, dim=-1)
        sel_vals, sel_idx = vals[:, :top_k], idx[:, :top_k]

        # 4. anti-route: swap in the next band of experts for a random subset of tokens
        if self.anti_route and want >= 2 * top_k:
            p = d * self.anti_route
            swap = (self.noise.rand(T, device=dev) < p)[:, None]
            alt_vals, alt_idx = vals[:, top_k : 2 * top_k], idx[:, top_k : 2 * top_k]
            sel_vals = torch.where(swap, alt_vals, sel_vals)
            sel_idx = torch.where(swap, alt_idx, sel_idx)

        keep = torch.ones_like(sel_vals)
        # 5. top-k reduction: starve capacity by keeping only the top-ranked expert
        if self.topk_reduce_at is not None and d >= self.topk_reduce_at and top_k > 1:
            keep[:, 1:] = 0.0

        # 6. renormalise over what survives selection
        w = sel_vals * keep
        w = w / w.sum(dim=-1, keepdim=True).clamp_min(1e-9)

        # 7. expert dropout: genuine lost capacity, so no redistribution
        if self.expert_dropout:
            drop = self.noise.rand(*w.shape, device=dev) < (d * self.expert_dropout)
            w = w.masked_fill(drop, 0.0)

        return w, sel_idx


class RouterLogitRecorder(Intervention):
    """Read-only probe: captures per-layer expert distributions for routing-KL.

    Always inert (never perturbs), so it can be installed on the sober reference and
    the impaired run alike without changing either.
    """

    kind = "router_recorder"
    requires = ("moe",)

    def __init__(self) -> None:
        super().__init__(seed=0)
        self._hooks = HookHandleManager()
        self.per_layer: dict[int, list[torch.Tensor]] = {}

    @property
    def inert(self) -> bool:
        return True

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        for layer_idx, gate in meta.routers(model):
            self._hooks.add(gate.register_forward_hook(self._make(layer_idx)))
        self._installed = True

    def remove(self) -> None:
        self._hooks.remove_all()
        self._installed = False

    def clear(self) -> None:
        self.per_layer.clear()

    def _make(self, layer_idx: int):
        def hook(module, args, output):
            logits = output[0] if isinstance(output, tuple) else output
            if isinstance(logits, torch.Tensor):
                p = F.softmax(logits.float().detach(), dim=-1).cpu()
                self.per_layer.setdefault(layer_idx, []).append(p)
            return output

        return hook
