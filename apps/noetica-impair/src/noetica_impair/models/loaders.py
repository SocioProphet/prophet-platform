"""Model loading. Local weights only -- invariant 0.6: no network inference calls.

Device selection is deliberate rather than assumed: the estate has CUDA accelerator
planes and the dev box is Apple/MPS, and the same rig has to run on both. Anything
device-specific lives here, not in the hooks.

Toy loaders build randomly-initialised tiny configs so the full invariant test suite
runs on CPU in seconds with no weights on disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import torch

from .registry import ArchMeta, get


def pick_device(prefer: str | None = None) -> torch.device:
    if prefer:
        return torch.device(prefer)
    env = os.environ.get("NOETICA_IMPAIR_DEVICE")
    if env:
        return torch.device(env)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def default_dtype(device: torch.device) -> torch.dtype:
    if device.type == "cuda":
        return torch.bfloat16
    if device.type == "mps":
        return torch.float16
    return torch.float32


@dataclass
class LoadedModel:
    model: torch.nn.Module
    meta: ArchMeta
    tokenizer: Any | None
    device: torch.device
    dtype: torch.dtype
    weights_ref: str  # local path or toy marker, recorded in provenance


def load(
    key: str,
    *,
    device: str | None = None,
    dtype: torch.dtype | None = None,
    local_path: str | None = None,
    quantization: str | None = None,
    seed: int = 0,
) -> LoadedModel:
    meta = get(key)
    if meta.hf_id.startswith("__toy_"):
        return _load_toy(meta, seed=seed, device=device)

    from transformers import AutoModelForCausalLM, AutoTokenizer

    src = local_path or os.environ.get("NOETICA_IMPAIR_WEIGHTS_DIR")
    if src is None:
        raise RuntimeError(
            f"{key}: refusing to fetch weights implicitly. Invariant 0.6 is local-only; "
            "pass local_path= or set NOETICA_IMPAIR_WEIGHTS_DIR to a directory holding "
            f"{meta.hf_id}."
        )
    if os.path.isdir(src) and not os.path.exists(os.path.join(src, "config.json")):
        src = os.path.join(src, meta.hf_id.split("/")[-1])

    dev = torch.device(device) if device else pick_device()
    dt = dtype or default_dtype(dev)

    kwargs: dict[str, Any] = {"dtype": dt, "local_files_only": True}
    if quantization in {"4bit", "8bit"}:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=quantization == "4bit", load_in_8bit=quantization == "8bit"
        )
        kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(src, **kwargs)
    if "device_map" not in kwargs:
        model = model.to(dev)
    model.eval()
    tok = AutoTokenizer.from_pretrained(src, local_files_only=True)
    return LoadedModel(model, meta, tok, dev, dt, weights_ref=str(src))


class ByteTokenizer:
    """Byte-level tokenizer for the toy fixtures (vocab 256).

    Exists so the FULL pipeline -- battery, drivers, sweep, provenance -- is
    exercisable on CPU without weights. It makes the plumbing testable; it does NOT
    make results from a randomly-initialised model meaningful, and nothing here should
    ever be read as a finding.
    """

    eos_token_id = 0
    pad_token_id = 0

    def __call__(self, text: str, return_tensors: str | None = None,
                 add_special_tokens: bool = False):
        ids = list(text.encode("utf-8")[:2048]) or [0]
        t = torch.tensor([ids], dtype=torch.long)
        return type("Enc", (), {"input_ids": t})()

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        vals = [int(i) for i in ids if not (skip_special_tokens and int(i) == 0)]
        return bytes(vals).decode("utf-8", errors="replace")


def _load_toy(meta: ArchMeta, *, seed: int, device: str | None) -> LoadedModel:
    from transformers import AutoModelForCausalLM, LlamaConfig, MixtralConfig

    torch.manual_seed(seed)
    common = dict(
        vocab_size=256, hidden_size=64, intermediate_size=128,
        num_hidden_layers=meta.n_layers, num_attention_heads=4,
        num_key_value_heads=2, max_position_embeddings=512,
    )
    if meta.is_moe:
        cfg = MixtralConfig(
            **common,
            num_local_experts=meta.moe.n_experts,
            num_experts_per_tok=meta.moe.top_k,
        )
    else:
        cfg = LlamaConfig(**common)
    model = AutoModelForCausalLM.from_config(cfg).eval()
    dev = torch.device(device) if device else torch.device("cpu")
    model = model.to(dev)
    return LoadedModel(model, meta, ByteTokenizer(), dev, torch.float32,
                       weights_ref=meta.hf_id)
