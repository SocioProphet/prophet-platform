"""Model registry: key -> loader + architecture metadata (work order section 2).

Hook attachment points differ per architecture and MUST NOT be hardcoded across
models. Every entry carries module *path templates*; interventions resolve them
through ``ArchMeta`` accessors, so adding a model is a registry edit, never a hook
edit.

Contrast-pair rule: ``dolphin-*`` and ``white-rabbit-neo`` are not standalone
subjects. Each declares ``pairs_with`` naming its exact sober base, and is only ever
run head-to-head against it. The measured quantity is the delta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import torch


class ArchError(RuntimeError):
    pass


def _resolve(root: torch.nn.Module, path: str) -> Any:
    obj: Any = root
    for part in path.split("."):
        if part.isdigit():
            obj = obj[int(part)]
        else:
            if not hasattr(obj, part):
                raise ArchError(f"module path {path!r} broke at {part!r} on {type(obj).__name__}")
            obj = getattr(obj, part)
    return obj


@dataclass(frozen=True)
class MoEInfo:
    n_experts: int
    top_k: int
    has_shared_experts: bool = False


@dataclass(frozen=True)
class ArchMeta:
    key: str
    hf_id: str
    arch: str  # "dense" | "moe"
    n_layers: int
    has_sae: bool = False
    moe: MoEInfo | None = None
    role: str = ""
    pairs_with: str | None = None
    # module path templates
    decoder_layers_path: str = "model.layers"
    lm_head_path: str = "lm_head"
    attn_path: str = "self_attn"          # relative to a decoder layer
    router_path: str | None = None        # relative to a decoder layer, MoE only
    sae_release: str | None = None
    # Gemma Scope source lock, pinned to match superconscious's
    # docs/interpretability-harness-architecture.md. These are not free parameters:
    # a feature index only means something against an exact SAE artifact.
    sae_layer: int | None = None
    sae_width: str | None = None
    sae_average_l0: str | None = None
    notes: str = ""

    @property
    def is_moe(self) -> bool:
        return self.arch == "moe"

    def decoder_layers(self, model: torch.nn.Module) -> Any:
        return _resolve(model, self.decoder_layers_path)

    def lm_head(self, model: torch.nn.Module) -> torch.nn.Module:
        return _resolve(model, self.lm_head_path)

    def attentions(self, model: torch.nn.Module) -> list[torch.nn.Module]:
        return [_resolve(l, self.attn_path) for l in self.decoder_layers(model)]

    def routers(self, model: torch.nn.Module) -> list[tuple[int, torch.nn.Module]]:
        """(layer_idx, gate_module) for every routed-expert gate.

        DeepSeek split rule: this returns the *routed* gate only. Shared experts are a
        separate module and are never returned here, so "never touch shared experts"
        holds structurally rather than by discipline.
        """
        if not self.is_moe or self.router_path is None:
            return []
        out = []
        for i, layer in enumerate(self.decoder_layers(model)):
            try:
                out.append((i, _resolve(layer, self.router_path)))
            except ArchError:
                continue  # dense layer in a hybrid stack
        return out

    def infer_n_layers(self, model: torch.nn.Module) -> int:
        try:
            return len(self.decoder_layers(model))
        except ArchError:
            return self.n_layers


REGISTRY: dict[str, ArchMeta] = {}


def register(meta: ArchMeta) -> ArchMeta:
    REGISTRY[meta.key] = meta
    return meta


def get(key: str) -> ArchMeta:
    if key not in REGISTRY:
        raise KeyError(f"unknown model key {key!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[key]


# --- the four rigs + contrast pairs -------------------------------------------

register(ArchMeta(
    key="gemma2-9b", hf_id="google/gemma-2-9b-it", arch="dense", n_layers=42,
    has_sae=True, role="SAE reference rig",
    # Source lock copied verbatim from superconscious's interpretability harness. The
    # instruction-tuned model and the matching it-res SAE are the estate's pinned pair;
    # using the base model with pt-res SAEs would silently unpin every feature id.
    sae_release="google/gemma-scope-9b-it-res",
    sae_layer=20, sae_width="131k", sae_average_l0="average_l0_81",
    notes="Gemma Scope plug-and-play; attn logit softcapping handled in attention.py",
))

register(ArchMeta(
    key="llama31-8b", hf_id="meta-llama/Llama-3.1-8B", arch="dense", n_layers=32,
    role="control surface",
    notes="ubiquitous tooling; if a result does not replicate here, suspect the method",
))

register(ArchMeta(
    key="mixtral-8x7b", hf_id="mistralai/Mixtral-8x7B-v0.1", arch="moe", n_layers=32,
    moe=MoEInfo(n_experts=8, top_k=2, has_shared_experts=False),
    role="legible router rig", router_path="mlp.gate",
    notes="transformers>=5: gate returns (router_logits, router_scores, router_indices)",
))

register(ArchMeta(
    key="gpt-oss-20b", hf_id="openai/gpt-oss-20b", arch="moe", n_layers=24,
    moe=MoEInfo(n_experts=32, top_k=4, has_shared_experts=False),
    role="OpenAI's own open-weights reference (see models.pairing)",
    router_path="mlp.router",
    notes="Apache 2.0 and UNGATED, unlike Gemma/Llama -- so it is the only reference "
          "rig runnable without an accepted HF licence. 24 layers, 32 experts, top-4. "
          "It is the same-lab ruler for GPT black-box readings, and being MoE it also "
          "carries a router for the routing-KL readout. No SAE exists for it, so "
          "SAE-dependent presets still skip here.",
))

register(ArchMeta(
    key="deepseek-r1-distill", hf_id="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    arch="dense", n_layers=32, role="split rig (distill fallback)",
    notes="OPEN FORK 10.1 default: R1 distill. NB the Llama distill is DENSE -- it has "
          "no router, so MoE ops skip. Use a true MoE DeepSeek for the shared/routed "
          "split result; see deepseek-v3 entry.",
))

register(ArchMeta(
    key="deepseek-v3", hf_id="deepseek-ai/DeepSeek-V3", arch="moe", n_layers=61,
    moe=MoEInfo(n_experts=256, top_k=8, has_shared_experts=True),
    role="split rig", router_path="mlp.gate",
    notes="PFC-first for free: perturb routed experts, leave shared untouched. Heavy.",
))

register(ArchMeta(
    # org renamed from cognitivecomputations -> dphn (old id 307s)
    key="dolphin-mixtral", hf_id="dphn/dolphin-2.7-mixtral-8x7b",
    arch="moe", n_layers=32, moe=MoEInfo(n_experts=8, top_k=2), router_path="mlp.gate",
    role="contrast pair", pairs_with="mixtral-8x7b",
    notes="never standalone; run head-to-head vs its own sober base",
))

register(ArchMeta(
    key="white-rabbit-neo", hf_id="WhiteRabbitNeo/WhiteRabbitNeo-13B-v1",
    arch="dense", n_layers=40, role="contrast pair", pairs_with="llama31-8b",
    notes="pin the exact sober base this fine-tune derives from before trusting the delta",
))

# --- toy architectures: the whole test suite runs on these, CPU-only ----------
# The rig's correctness is a property of the hooks, not of the weights, so M0-M4
# are provable on a laptop while real weights run on an accelerator plane.

register(ArchMeta(
    key="toy-dense", hf_id="__toy_llama__", arch="dense", n_layers=4,
    role="test fixture (random init, CPU)",
))

register(ArchMeta(
    key="toy-moe", hf_id="__toy_mixtral__", arch="moe", n_layers=4,
    moe=MoEInfo(n_experts=8, top_k=2), router_path="mlp.gate",
    role="test fixture (random init, CPU)",
))
