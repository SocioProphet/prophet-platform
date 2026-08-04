"""Deterministic fixtures for the attribution contract.

These stand in for real discovery artifacts. A production signature comes from
:func:`noetica_impair.provenance.features.discover` on real gemma-2-9b-it L20
activations; that path needs weights and torch and is exercised elsewhere. Here we
synthesise model-distinct fingerprints deterministically so the CONTRACT — distance,
provenance binding, accept/reject gates — is testable on any machine with no weights.

Seeding uses SHA-256 of the ``(model_id, concept, salt)`` string, not Python's
``hash()`` (which is per-process salted), so the fixtures are identical on every run
and every machine.
"""

from __future__ import annotations

import hashlib
import random
from typing import Sequence

from ..provenance.contrasts import CONTRASTS
from .signature import LatentSignature, mint_signature

SAE_WIDTH = 16384
TOP_K = 32
CONCEPTS: tuple[str, ...] = tuple(sorted(CONTRASTS))


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:16], 16)


def _draw_ids(model_id: str, concept: str, *, salt: str, width: int, top_k: int) -> list[int]:
    rng = random.Random(_seed(model_id, concept, salt))
    return rng.sample(range(width), top_k)


def synthetic_signature(
    model_id: str,
    *,
    salt: str = "",
    width: int = SAE_WIDTH,
    top_k: int = TOP_K,
    concepts: Sequence[str] = CONCEPTS,
    contrast_sha: str = "sha256:fixture",
    mint: bool = True,
) -> LatentSignature:
    """A deterministic, model-distinct signature over the real concept vocabulary."""
    fp = {c: _draw_ids(model_id, c, salt=salt, width=width, top_k=top_k) for c in concepts}
    sig = LatentSignature(
        model_id=model_id,
        layer=20,
        contrast_sha=contrast_sha,
        feature_artifact_version=f"{model_id}-L20-fixture",
        fingerprint=fp,
        sae_release="fixture",
    )
    return mint_signature(sig) if mint else sig


def remeasure(
    sig: LatentSignature,
    *,
    fraction: float = 0.25,
    salt: str = "remeasure",
    width: int = SAE_WIDTH,
    mint: bool = True,
) -> LatentSignature:
    """A noisy re-measurement of the SAME model: most ids kept, a fraction resampled.

    Models the run-to-run drift a genuine second discovery pass would show — it must
    still attribute to the same model.
    """
    rng = random.Random(_seed(sig.model_id, "remeasure", salt))
    new_fp: dict[str, list[int]] = {}
    for concept, ids in sig.fingerprint.items():
        k = int(len(ids) * fraction)
        keep = list(ids)
        pool = [i for i in range(width) if i not in set(ids)]
        swap_idx = rng.sample(range(len(keep)), min(k, len(keep)))
        fresh = rng.sample(pool, len(swap_idx))
        for pos, val in zip(swap_idx, fresh):
            keep[pos] = val
        new_fp[concept] = keep
    out = LatentSignature(
        model_id=sig.model_id,
        layer=sig.layer,
        contrast_sha=sig.contrast_sha,
        feature_artifact_version=sig.feature_artifact_version + "-remeasure",
        fingerprint=new_fp,
        sae_release=sig.sae_release,
    )
    return mint_signature(out) if mint else out


def forged_signature(
    claim_model_id: str,
    *,
    salt: str = "forgery",
    mint: bool = True,
) -> LatentSignature:
    """An impostor claiming to be ``claim_model_id`` but with an unrelated fingerprint."""
    return synthetic_signature(claim_model_id, salt=salt, mint=mint)


DEFAULT_MODELS = ("gemma-2-9b-it", "llama-3.1-8b", "qwen2.5-7b", "mistral-7b-v0.3")


def build_registry(model_ids: Sequence[str] = DEFAULT_MODELS):
    """Mint + enrol a signature for each model. Returns a populated registry."""
    from .verify import SignatureRegistry

    reg = SignatureRegistry()
    for mid in model_ids:
        reg.enrol(synthetic_signature(mid))
    return reg
