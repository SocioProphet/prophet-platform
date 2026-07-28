"""Feature-ID discovery artifact (work order section 5).

A preset that references SAE features is only reproducible against a PINNED
discovery run. This module owns that pin: concept -> ranked feature ids, plus the
hash of the contrast set that produced them and a version string the preset records.

Discovery is contrastive: for each concept, encode residuals for a concept-present
and a concept-absent prompt set through the SAE and rank features by mean activation
difference (present - absent). Rank order is meaningful downstream -- SelfMonitorAblation
ablates the first round(d*n) features, most discriminative first.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import torch

CONCEPTS = (
    "hedging_caution",
    "error_aversion",
    "reward_value",
    "salience",
    "threat_tom",
    "consistency",
    # MDMA needs these two, and neither is a rename of the above: "affiliation" is
    # prosocial valuation (distinct from generic reward/value), and "refusal_guard" is
    # the trained defensive posture (distinct from epistemic hedging/caution).
    "affiliation",
    "refusal_guard",
    # Ego dissolution (psilocin's 5-HT1A/transporter limb) needs a self-reference
    # direction to suppress. Distinct from "consistency", which is about agreeing with
    # your own prior assertions rather than about referring to yourself at all.
    "self_reference",
)


def contrast_hash(pairs: dict[str, tuple[Sequence[str], Sequence[str]]]) -> str:
    blob = json.dumps(
        {k: [list(v[0]), list(v[1])] for k, v in sorted(pairs.items())},
        sort_keys=True, ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


@dataclass
class FeatureArtifact:
    version: str
    model_key: str
    sae_release: str | None
    contrast_sha: str
    top_n: int
    concepts: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_ts: float = field(default_factory=time.time)
    _sae_cache: dict[int, Any] = field(default_factory=dict, repr=False)

    def add(self, concept: str, layer: int, ids: Sequence[int], scores: Sequence[float]) -> None:
        self.concepts[concept] = {
            "layer": int(layer),
            "feature_ids": [int(i) for i in ids],
            "scores": [float(s) for s in scores],
        }

    def resolve(self, concept: str, layer: int | None = None) -> tuple[Any, list[int]]:
        if concept not in self.concepts:
            raise KeyError(concept)
        entry = self.concepts[concept]
        lyr = layer if layer is not None else entry["layer"]
        sae = self._sae_cache.get(lyr)
        if sae is None:
            raise RuntimeError(
                f"no SAE bound for layer {lyr}; call bind_sae(layer, sae) after loading "
                "the artifact -- the artifact stores feature ids, never weights"
            )
        return sae, list(entry["feature_ids"])

    def bind_sae(self, layer: int, sae: Any) -> None:
        self._sae_cache[layer] = sae

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version, "model_key": self.model_key,
            "sae_release": self.sae_release, "contrast_sha": self.contrast_sha,
            "top_n": self.top_n, "created_ts": self.created_ts, "concepts": self.concepts,
        }

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))
        return p

    @classmethod
    def load(cls, path: str | Path) -> "FeatureArtifact":
        d = json.loads(Path(path).read_text())
        art = cls(version=d["version"], model_key=d["model_key"], sae_release=d.get("sae_release"),
                  contrast_sha=d["contrast_sha"], top_n=d["top_n"],
                  created_ts=d.get("created_ts", 0.0))
        art.concepts = d["concepts"]
        return art


def _ids_from(enc: Any) -> torch.Tensor | None:
    """Pull input_ids out of whatever the tokenizer returned.

    HF BatchEncoding, a plain dict, an object with .input_ids (the toy fixtures), or a
    bare tensor/list are all in play. Handle them explicitly rather than duck-typing on
    __getitem__, which silently matches the wrong thing.
    """
    obj = getattr(enc, "input_ids", None)
    if obj is None and isinstance(enc, dict):
        obj = enc.get("input_ids")
    if obj is None:
        obj = enc
    if isinstance(obj, torch.Tensor):
        return obj
    if isinstance(obj, (list, tuple)):
        return torch.as_tensor(obj, dtype=torch.long)
    return None


def _tokenize(lm: Any, text: str, max_len: int) -> torch.Tensor:
    """Tokenize with the full HF surface when available, else a minimal one.

    The CPU toy models carry a byte tokenizer with no truncation/padding kwargs, and
    the discovery pipeline must be exercisable there -- otherwise the only way to test
    this path is on a GPU plane, which is how untested paths happen.
    """
    tok = lm.tokenizer
    ids = None
    try:
        ids = _ids_from(tok(text, return_tensors="pt", truncation=True, max_length=max_len))
    except TypeError:
        ids = None
    if ids is None:
        try:
            ids = _ids_from(tok(text, return_tensors="pt"))
        except TypeError:
            ids = _ids_from(tok(text))
    if ids is None:
        raise TypeError(f"could not obtain input_ids from {type(tok).__name__}")
    if ids.dim() == 1:
        ids = ids.unsqueeze(0)
    return ids[:, :max_len]


@torch.no_grad()
def residual_encoder(lm: Any, layer: int, *, max_len: int = 64):
    """Build ``encode_residuals(prompts) -> Tensor[n, seq, d_model]`` for a loaded model.

    Reads the residual stream at the OUTPUT of decoder layer ``layer`` -- the same site
    FeatureSteering edits, so discovered ids and applied steers refer to the same space.
    Padding positions are dropped rather than averaged in: a pad token is not evidence
    about a concept, and with short minimal pairs they would otherwise dominate.
    """
    captured: dict[str, torch.Tensor] = {}
    layers = lm.meta.decoder_layers(lm.model)
    if not (0 <= layer < len(layers)):
        raise ValueError(f"layer {layer} out of range for {len(layers)}-layer model")

    def hook(module, args, output):
        captured["h"] = (output[0] if isinstance(output, tuple) else output).detach()

    def encode(prompts: Sequence[str]) -> torch.Tensor:
        handle = layers[layer].register_forward_hook(hook)
        try:
            out = []
            for text in prompts:                      # one at a time: no pad positions
                ids = _tokenize(lm, text, max_len).to(lm.device)
                captured.clear()
                lm.model(ids)
                h = captured.get("h")
                if h is None:
                    raise RuntimeError("residual hook did not fire")
                out.append(h[0].float().cpu())        # (seq, d_model)
            return out                                 # ragged: list of (seq, d_model)
        finally:
            handle.remove()

    return encode


def _stack_mean_activation(sae: Any, residuals: Any, ids: torch.Tensor | None = None
                           ) -> torch.Tensor:
    """Mean SAE activation over every real token position of every prompt."""
    if isinstance(residuals, torch.Tensor):
        residuals = [residuals.flatten(0, -2)]
    acc = None
    n = 0
    for h in residuals:
        f = sae.encode(h if h.dim() == 2 else h.flatten(0, -2)).float()
        s = f.sum(0)
        acc = s if acc is None else acc + s
        n += f.shape[0]
    if acc is None or n == 0:
        raise ValueError("no residuals to encode")
    return acc / n


def split_half_reliability(
    *, encode_residuals, sae: Any, present: Sequence[str], absent: Sequence[str],
    top_n: int, seed: int = 0,
) -> dict[str, Any]:
    """Would this feature set survive being computed on a different half of the prompts?

    Discovery always returns a top-N list -- on pure noise just as readily as on a real
    concept. The list alone therefore carries no evidence that anything was found. This
    splits the pairs into halves, ranks each independently, and reports the overlap of
    the two top-N sets plus the Spearman-style rank agreement.

    Low overlap means the ranking is dominated by sampling noise, and an artifact built
    on it would be a reproducible way of steering nothing in particular.
    """
    import random
    n_pairs = min(len(present), len(absent))
    idx = list(range(n_pairs))
    random.Random(seed).shuffle(idx)
    a_idx, b_idx = idx[: n_pairs // 2], idx[n_pairs // 2:]
    if not a_idx or not b_idx:
        return {"overlap": float("nan"), "n_pairs": n_pairs, "checkable": False}

    def rank(sub: list[int]) -> torch.Tensor:
        p = _stack_mean_activation(sae, encode_residuals([present[i] for i in sub]))
        q = _stack_mean_activation(sae, encode_residuals([absent[i] for i in sub]))
        return (p - q).float()

    da, db = rank(a_idx), rank(b_idx)
    k = min(top_n, da.numel())
    ta = set(torch.topk(da, k).indices.tolist())
    tb = set(torch.topk(db, k).indices.tolist())
    overlap = len(ta & tb) / k
    # correlation across the FULL score vector, not just the top-k
    va, vb = da - da.mean(), db - db.mean()
    denom = (va.norm() * vb.norm()).clamp_min(1e-12)
    corr = float((va @ vb) / denom)
    return {
        "overlap": overlap, "rank_correlation": corr, "top_n": k,
        "n_pairs": n_pairs, "half_sizes": [len(a_idx), len(b_idx)], "checkable": True,
    }


@torch.no_grad()
def discover(
    *,
    encode_residuals,
    sae,
    layer: int,
    pairs: dict[str, tuple[Sequence[str], Sequence[str]]],
    model_key: str,
    sae_release: str | None,
    top_n: int = 32,
    version: str | None = None,
    reliability: bool = True,
    seed: int = 0,
) -> FeatureArtifact:
    """Rank features by contrastive activation difference.

    ``encode_residuals(prompts) -> Tensor[n_prompts, seq, d_model]`` is supplied by the
    caller so this stays independent of how the model is being run.
    """
    csha = contrast_hash(pairs)
    ver = version or f"{model_key}-L{layer}-{csha[7:19]}"
    art = FeatureArtifact(version=ver, model_key=model_key, sae_release=sae_release,
                          contrast_sha=csha, top_n=top_n)
    art.bind_sae(layer, sae)

    for concept, (present, absent) in pairs.items():
        a = _stack_mean_activation(sae, encode_residuals(present))
        b = _stack_mean_activation(sae, encode_residuals(absent))
        diff = (a - b).float()
        k = min(top_n, diff.numel())
        scores, ids = torch.topk(diff, k)
        art.add(concept, layer, ids.tolist(), scores.tolist())

        # A top-N list exists even on pure noise, so the list alone is not evidence.
        # Record whether it survives being computed on a different half of the prompts.
        if reliability:
            art.concepts[concept]["reliability"] = split_half_reliability(
                encode_residuals=encode_residuals, sae=sae,
                present=list(present), absent=list(absent), top_n=k, seed=seed,
            )
    return art


def reliability_report(art: "FeatureArtifact", *, min_overlap: float = 0.30
                       ) -> tuple[bool, list[str]]:
    """Which concepts are too unstable to pin a preset on."""
    problems: list[str] = []
    for concept, entry in sorted(art.concepts.items()):
        rel = entry.get("reliability")
        if not rel or not rel.get("checkable"):
            problems.append(f"{concept}: reliability not measured")
            continue
        ov = rel.get("overlap", 0.0)
        if ov < min_overlap:
            problems.append(
                f"{concept}: split-half overlap {ov:.2f} < {min_overlap:.2f} -- the "
                "ranking is dominated by sampling noise, so steering these ids would "
                "be a reproducible way of steering nothing in particular"
            )
    return (not problems), problems
