"""Attention-score interventions (work order 3.1, 3.2).

transformers >= 5 dispatches attention through a pluggable interface and defaults to
SDPA, which never materialises the score matrix -- so a plain forward hook cannot see
pre-softmax scores. We therefore register our own attention function that reproduces
the eager math and exposes a score-edit point.

CRITICAL: a custom attention function must ALSO register a mask function under the
same name. Without it, mask creation falls through to the SDPA path, which returns
``None`` (SDPA applies causality internally via ``is_causal``) -- and an eager
kernel receiving ``attention_mask=None`` attends bidirectionally. That silently
turns every "sober" baseline into a non-causal model. Measured on a toy Llama:
6.7e-08 max logit divergence with the mask registered, 2.5e-01 without.

Score edits are applied AFTER scaling and softcapping but BEFORE the causal mask is
added, so an edit can never resurrect a masked position, and multiplicative edits
(3.2) never divide a -inf sentinel.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

import torch
import torch.nn.functional as F
from transformers.masking_utils import AttentionMaskInterface, eager_mask
from transformers.modeling_utils import AttentionInterface

from .base import HookHandleManager, Intervention

ATTN_IMPL_NAME = "noetica_impair"


class ScoreEdit(Protocol):
    def __call__(
        self, scores: torch.Tensor, *, layer_idx: int, q_pos: torch.Tensor, k_pos: torch.Tensor
    ) -> torch.Tensor: ...


class ScoreEditor:
    """Per-model registry of score edits, attached to each attention module.

    Held on the module (not a global) so several models can be rigged in one process.
    """

    def __init__(self) -> None:
        self._edits: list[ScoreEdit] = []

    def register(self, fn: ScoreEdit) -> None:
        self._edits.append(fn)

    def unregister(self, fn: ScoreEdit) -> None:
        if fn in self._edits:
            self._edits.remove(fn)

    def apply(self, scores: torch.Tensor, layer_idx: int) -> torch.Tensor:
        if not self._edits:
            return scores
        q_len, k_len = scores.shape[-2], scores.shape[-1]
        # Absolute query positions: with a KV cache q_len==1 while k_len grows, so
        # the query's true index is offset by the cached prefix.
        offset = k_len - q_len
        q_pos = torch.arange(q_len, device=scores.device) + offset
        k_pos = torch.arange(k_len, device=scores.device)
        for fn in self._edits:
            scores = fn(scores, layer_idx=layer_idx, q_pos=q_pos, k_pos=k_pos)
        return scores


def _repeat_kv(x: torch.Tensor, n_rep: int) -> torch.Tensor:
    if n_rep == 1:
        return x
    b, n_kv, s, d = x.shape
    return x[:, :, None].expand(b, n_kv, n_rep, s, d).reshape(b, n_kv * n_rep, s, d)


def impaired_attention_forward(
    module: torch.nn.Module,
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    attention_mask: torch.Tensor | None,
    scaling: float | None = None,
    dropout: float = 0.0,
    **kwargs: Any,
) -> tuple[torch.Tensor, torch.Tensor]:
    if scaling is None:
        scaling = getattr(module, "scaling", None)
        if scaling is None:
            scaling = query.shape[-1] ** -0.5

    n_rep = getattr(module, "num_key_value_groups", 1)
    key_states = _repeat_kv(key, n_rep)
    value_states = _repeat_kv(value, n_rep)

    scores = torch.matmul(query, key_states.transpose(2, 3)) * scaling

    # Gemma-2 style logit softcapping, applied on raw scores before masking.
    softcap = getattr(module, "attn_logit_softcapping", None)
    if softcap is None:
        softcap = getattr(getattr(module, "config", None), "attn_logit_softcapping", None)
    if softcap is not None:
        scores = torch.tanh(scores / softcap) * softcap

    editor: ScoreEditor | None = getattr(module, "_noetica_editor", None)
    if editor is not None:
        scores = editor.apply(scores, getattr(module, "layer_idx", 0))

    if attention_mask is not None:
        scores = scores + attention_mask[:, :, :, : key_states.shape[-2]]

    scores = F.softmax(scores, dim=-1, dtype=torch.float32).to(query.dtype)
    scores = F.dropout(scores, p=dropout, training=module.training)
    out = torch.matmul(scores, value_states)
    return out.transpose(1, 2).contiguous(), scores


_REGISTERED = False


def ensure_registered() -> str:
    """Register the impaired attention function and its mask counterpart (once)."""
    global _REGISTERED
    if not _REGISTERED:
        AttentionInterface.register(ATTN_IMPL_NAME, impaired_attention_forward)
        # Without this the SDPA mask path yields None -> bidirectional attention.
        AttentionMaskInterface.register(ATTN_IMPL_NAME, eager_mask)
        _REGISTERED = True
    return ATTN_IMPL_NAME


def attach_editor(model: torch.nn.Module) -> ScoreEditor:
    """Switch the model onto the impaired attention impl and attach a shared editor."""
    ensure_registered()
    editor: ScoreEditor | None = getattr(model, "_noetica_editor", None)
    if editor is None:
        editor = ScoreEditor()
        model._noetica_editor = editor  # type: ignore[assignment]
        for mod in model.modules():
            if _is_attention(mod):
                mod._noetica_editor = editor  # type: ignore[assignment]
        if getattr(model.config, "_attn_implementation", None) != ATTN_IMPL_NAME:
            model.set_attn_implementation(ATTN_IMPL_NAME)
    return editor


def _is_attention(mod: torch.nn.Module) -> bool:
    return hasattr(mod, "num_key_value_groups") or type(mod).__name__.endswith("Attention")


class _AttentionScoreIntervention(Intervention):
    """Shared plumbing: register one edit callback with the model's ScoreEditor."""

    def __init__(self, *, layers: tuple[int, ...] | None = None, seed: int = 0) -> None:
        super().__init__(seed=seed)
        self.layers = layers
        self._editor: ScoreEditor | None = None
        self._hooks = HookHandleManager()

    def install(self, model: torch.nn.Module, meta: Any) -> None:
        self._editor = attach_editor(model)
        self._editor.register(self._edit)
        self._installed = True

    def remove(self) -> None:
        if self._editor is not None:
            self._editor.unregister(self._edit)
        self._hooks.remove_all()
        self._installed = False

    def _in_scope(self, layer_idx: int) -> bool:
        return self.layers is None or layer_idx in self.layers

    def _edit(
        self, scores: torch.Tensor, *, layer_idx: int, q_pos: torch.Tensor, k_pos: torch.Tensor
    ) -> torch.Tensor:
        raise NotImplementedError


class DistanceDecayAttenuation(_AttentionScoreIntervention):
    """3.1 -- working-memory lesion.

    ``S[i,j] -= d * alpha * relu(|i-j| - window)``

    ``window`` protects local context so grammar survives while recall over distance
    degrades. Renormalisation is the model's own softmax.
    """

    kind = "attn_distance_decay"

    def __init__(self, *, alpha: float, window: int = 8, layers=None, seed: int = 0) -> None:
        super().__init__(layers=layers, seed=seed)
        self.alpha = float(alpha)
        self.window = int(window)

    def _magnitudes_nonzero(self) -> bool:
        return self.alpha != 0.0

    def _params(self) -> dict[str, Any]:
        return {"alpha": self.alpha, "window": self.window, "layers": self.layers}

    def _edit(self, scores, *, layer_idx, q_pos, k_pos):
        if self.inert or not self._in_scope(layer_idx):
            return scores
        dist = (q_pos[:, None] - k_pos[None, :]).abs().to(scores.dtype)
        penalty = self.dose * self.alpha * torch.clamp(dist - self.window, min=0.0)
        return scores - penalty


class AttentionBroadening(_AttentionScoreIntervention):
    """3.2 -- cannabis-specific. Flattens the score distribution: ``S /= (1 + d*tau)``.

    Entropy up, focus divergent/tangential. Opposite sign to 3.1 on the same axis;
    ``substances.schema`` refuses any preset that enables both.
    """

    kind = "attn_broaden"

    def __init__(self, *, tau: float, layers=None, seed: int = 0) -> None:
        super().__init__(layers=layers, seed=seed)
        self.tau = float(tau)

    def _magnitudes_nonzero(self) -> bool:
        return self.tau != 0.0

    def _params(self) -> dict[str, Any]:
        return {"tau": self.tau, "layers": self.layers}

    def _edit(self, scores, *, layer_idx, q_pos, k_pos):
        if self.inert or not self._in_scope(layer_idx):
            return scores
        return scores / (1.0 + self.dose * self.tau)
