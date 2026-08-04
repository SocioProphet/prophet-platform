"""Latent signatures for zero-shot model attribution (prophet-workspace#76, item 4).

The research claim this operationalises
-------------------------------------
Paraphrases of one meaning converge to a compact *invariant zone* in a model's
latent space. The directions that MOVE meaning (semantic-changing, ``T^sem``) can be
separated from the directions that leave it fixed (nuisance, ``T^nuis``) by a
contrastive sensitivity decomposition. The estate already performs that
decomposition: :mod:`noetica_impair.provenance.features` ranks SAE features by the
mean activation difference between an index-aligned concept-PRESENT and
concept-ABSENT set (:mod:`noetica_impair.provenance.contrasts`), and the minimal-pair
discipline is exactly what holds ``T^nuis`` fixed so the ranked ids describe ``T^sem``.

Item 4's second half is the DUAL of :mod:`noetica_impair.readout.invariance`. There a
behavioural signature is only usable as a ruler if it is *invariant across labs*; the
model-specific part is a confound to be suppressed. Model attribution keeps precisely
that residual: WHICH features encode each concept is a property of the model+SAE
pipeline, so the ordered top-k feature ids per concept form a model-specific
fingerprint — a latent signature.

What this module is
-------------------
A **contract**, not a discovery pipeline. It defines the latent-signature record, a
deterministic distance between signatures, and the provenance binding — all stdlib
only, so it is verifiable in CI without weights or torch. The signature is built from
the dict a :class:`~noetica_impair.provenance.features.FeatureArtifact` already emits;
producing that artifact from real gemma-2-9b-it L20 activations is the existing
discovery pass and is deliberately NOT reimplemented here.

What is deliberately left as SPECIFY (filed as a research gap): the geometric
invariant-zone estimator (paraphrase-cloud covariance / tangent-space ``T^sem ⊕
T^nuis`` split as a continuous object rather than a ranked id set), and the empirical
threshold calibration on a real multi-model discovery corpus. The fingerprint here is
the id-set surrogate the estate can compute today.

Provenance is not a private log format: the receipt is minted through
:func:`noetica_impair.provenance.log.mint_receipt`, so a signature is a first-class
record in the estate's existing SHA-256 receipt chain (FIPS-180-4 the algorithm; no
FIPS-140 module is claimed) rather than a parallel one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..provenance.log import Receipt, mint_receipt, sha

SPEC_VERSION = "noetica-impair-attribution/0.1.0"


def _clean_fingerprint(fp: Mapping[str, Sequence[int]]) -> dict[str, list[int]]:
    """Canonical fingerprint: concept -> ordered top-k feature ids (rank preserved).

    Order is meaningful — most-discriminative first, the same order
    ``features.discover`` returns — so it is NOT sorted. Ids are de-duplicated keeping
    first occurrence, because a repeated id carries no extra geometry and would skew
    the overlap.
    """
    out: dict[str, list[int]] = {}
    for concept in sorted(fp):
        seen: set[int] = set()
        ordered: list[int] = []
        for i in fp[concept]:
            ii = int(i)
            if ii not in seen:
                seen.add(ii)
                ordered.append(ii)
        out[concept] = ordered
    return out


@dataclass
class LatentSignature:
    """A model's invariant-zone fingerprint plus the provenance that anchors it.

    ``fingerprint`` maps each probed concept to the ordered feature ids that carry its
    semantic-changing direction (``T^sem``) for this model+SAE. ``receipt`` binds the
    fingerprint and its provenance into the estate receipt chain: ``outputs_sha`` is
    the hash of the fingerprint, so tampering the fingerprint after minting is
    detectable, and ``id`` is the hash of the whole receipt body.
    """

    model_id: str
    layer: int
    contrast_sha: str
    feature_artifact_version: str
    fingerprint: dict[str, list[int]]
    sae_release: str | None = None
    scores: dict[str, list[float]] | None = None
    actor: str = "noetica-impair-attribution"
    spec_version: str = SPEC_VERSION
    receipt: dict[str, Any] | None = None

    # ── provenance / binding ──────────────────────────────────────────────────

    def provenance_body(self) -> dict[str, Any]:
        """The inputs side of the receipt: everything that produced the fingerprint
        EXCEPT the fingerprint itself."""
        return {
            "model_id": self.model_id,
            "layer": self.layer,
            "sae_release": self.sae_release,
            "contrast_sha": self.contrast_sha,
            "feature_artifact_version": self.feature_artifact_version,
            "spec_version": self.spec_version,
        }

    def fingerprint_body(self) -> dict[str, list[int]]:
        return dict(self.fingerprint)

    def concepts(self) -> tuple[str, ...]:
        return tuple(sorted(self.fingerprint))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "layer": self.layer,
            "contrast_sha": self.contrast_sha,
            "feature_artifact_version": self.feature_artifact_version,
            "fingerprint": self.fingerprint,
            "sae_release": self.sae_release,
            "scores": self.scores,
            "actor": self.actor,
            "spec_version": self.spec_version,
            "receipt": self.receipt,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "LatentSignature":
        return cls(
            model_id=d["model_id"],
            layer=int(d["layer"]),
            contrast_sha=d["contrast_sha"],
            feature_artifact_version=d["feature_artifact_version"],
            fingerprint=_clean_fingerprint(d["fingerprint"]),
            sae_release=d.get("sae_release"),
            scores=d.get("scores"),
            actor=d.get("actor", "noetica-impair-attribution"),
            spec_version=d.get("spec_version", SPEC_VERSION),
            receipt=d.get("receipt"),
        )

    @classmethod
    def from_feature_artifact(
        cls,
        art: Mapping[str, Any],
        *,
        top_k: int | None = None,
    ) -> "LatentSignature":
        """Build a signature from a ``FeatureArtifact.to_dict()`` payload.

        Takes the plain dict rather than the live object so this module never imports
        torch: attribution must be checkable on any machine, not only where a model
        loads. ``top_k`` truncates each concept's id list; ``None`` keeps them all.
        """
        fp: dict[str, list[int]] = {}
        scores: dict[str, list[float]] = {}
        for concept, entry in art.get("concepts", {}).items():
            ids = list(entry.get("feature_ids", []))
            scs = list(entry.get("scores", []))
            if top_k is not None:
                ids, scs = ids[:top_k], scs[:top_k]
            fp[concept] = ids
            if scs:
                scores[concept] = scs
        return cls(
            model_id=art["model_key"],
            layer=int(next(iter(art.get("concepts", {}).values()), {}).get("layer", -1)),
            contrast_sha=art["contrast_sha"],
            feature_artifact_version=art["version"],
            fingerprint=_clean_fingerprint(fp),
            sae_release=art.get("sae_release"),
            scores=scores or None,
        )


def mint_signature(
    sig: LatentSignature,
    *,
    project: str = "noetica-impair",
    backend: str = "local",
    status: str = "ok",
    epistemic_status: str = "measured",
    prev: str | None = None,
) -> LatentSignature:
    """Attach an estate receipt, binding provenance (inputs) and fingerprint (outputs).

    Reuses :func:`noetica_impair.provenance.log.mint_receipt` verbatim so the receipt
    is chain-compatible with every other receipt in the estate — an attribution record
    verifies under the gateway's own ``verify_chain``.
    """
    sig.fingerprint = _clean_fingerprint(sig.fingerprint)
    rcpt: Receipt = mint_receipt(
        project=project,
        kind="latent-signature",
        backend=backend,
        runtime=sig.spec_version,
        inputs=sig.provenance_body(),
        outputs=sig.fingerprint_body(),
        status=status,
        actor=sig.actor,
        epistemic_status=epistemic_status,
        prev=prev,
    )
    from dataclasses import asdict

    sig.receipt = asdict(rcpt)
    return sig


# ── distance ─────────────────────────────────────────────────────────────────


def _rank_weights(ids: Sequence[int]) -> dict[int, float]:
    """Rank-decayed weight per id: most-discriminative first counts most."""
    return {int(i): 1.0 / (r + 1.0) for r, i in enumerate(ids)}


def concept_overlap(a: Sequence[int], b: Sequence[int]) -> float:
    """Rank-weighted overlap of two ordered id lists, in [0, 1].

    Plain Jaccard treats the 1st and 32nd feature as equally important; the ranking is
    meaningful here (it is the order ``discover`` returns, most-discriminative first),
    so shared high-rank ids weigh more. Identical lists -> 1.0; disjoint -> 0.0.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    wa, wb = _rank_weights(a), _rank_weights(b)
    shared = set(wa) & set(wb)
    inter = sum(min(wa[i], wb[i]) for i in shared)
    union = sum(wa.values()) + sum(wb.values()) - sum(max(wa[i], wb[i]) for i in shared)
    return inter / union if union > 0 else 0.0


def signature_distance(a: LatentSignature, b: LatentSignature) -> float:
    """Distance in [0, 1] between two signatures: 1 - mean per-concept overlap.

    Concepts are unioned: a concept present in only one signature contributes 0
    overlap, so signatures probing different concept sets are correctly far apart. The
    measure is symmetric and deterministic — no floats beyond the id arithmetic, so two
    runs agree byte-for-byte.
    """
    concepts = set(a.fingerprint) | set(b.fingerprint)
    if not concepts:
        return 1.0
    total = 0.0
    for c in concepts:
        total += concept_overlap(a.fingerprint.get(c, []), b.fingerprint.get(c, []))
    return 1.0 - total / len(concepts)
