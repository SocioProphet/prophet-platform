"""Deterministic model-attribution verifier with teeth (prophet-workspace#76, item 4).

Given a candidate :class:`~noetica_impair.attribution.signature.LatentSignature` and a
registry of enrolled signatures, attribute the candidate to a model — and, crucially,
REFUSE to when it should not be attributed. Two independent gates, both fail-closed:

1. **Provenance integrity.** The candidate's receipt is recomputed from its body. If
   the fingerprint, the provenance, or any receipt field was altered after minting, the
   hashes no longer agree and attribution is refused before any distance is considered.
   A forged signature cannot borrow a genuine receipt.

2. **Geometric match.** The candidate is scored against every enrolled signature. It is
   attributed only if the nearest is within ``max_distance`` AND clears the runner-up by
   at least ``min_margin``. A signature that matches nothing (an impostor) or matches
   two models equally (ambiguous) is returned as an explicit non-attribution, never as
   the least-bad label. This mirrors :mod:`noetica_impair.readout.equivalence`, which
   reports the runner-up margin and turns "nothing matched" into an explicit no-match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..provenance.log import sha
from .signature import LatentSignature, signature_distance


def verify_signature_receipt(sig: LatentSignature) -> tuple[bool, str]:
    """Recompute the receipt and confirm the fingerprint/provenance were not altered.

    Returns ``(ok, reason)``. This is the estate's own receipt rule
    (:func:`noetica_impair.provenance.log.verify_chain`) applied to a single record,
    plus the two content bindings specific to a signature: ``outputs_sha`` must equal
    the hash of the current fingerprint and ``inputs_sha`` the hash of the current
    provenance.
    """
    r = sig.receipt
    if not r:
        return False, "signature carries no receipt (unprovenanced; refused)"
    try:
        body = {
            k: r[k]
            for k in (
                "project", "kind", "backend", "runtime", "inputs_sha", "outputs_sha",
                "status", "actor", "epistemic_status", "prev", "ts",
            )
        }
    except KeyError as e:
        return False, f"receipt missing field {e}; malformed"
    if sha(body) != r.get("id"):
        return False, "receipt id does not match its body (tampered)"
    if sha(sig.fingerprint_body()) != r["outputs_sha"]:
        return False, "fingerprint does not match receipt outputs_sha (forged/altered)"
    if sha(sig.provenance_body()) != r["inputs_sha"]:
        return False, "provenance does not match receipt inputs_sha (altered)"
    return True, "receipt verified: fingerprint and provenance intact"


@dataclass
class SignatureRegistry:
    """The enrolled reference signatures — one per known model."""

    signatures: dict[str, LatentSignature] = field(default_factory=dict)

    def enrol(self, sig: LatentSignature, *, require_receipt: bool = True) -> None:
        if require_receipt:
            ok, reason = verify_signature_receipt(sig)
            if not ok:
                raise ValueError(f"refusing to enrol {sig.model_id}: {reason}")
        self.signatures[sig.model_id] = sig

    def __len__(self) -> int:
        return len(self.signatures)


@dataclass
class AttributionResult:
    """The verdict, with every reason it might be weak attached to it."""

    attributed_model: str | None
    distance: float
    matched: bool
    receipt_ok: bool
    runner_up: tuple[str, float] | None = None
    ranked: list[tuple[str, float]] = field(default_factory=list)
    reason: str = ""

    @property
    def margin(self) -> float:
        """Gap to the runner-up. A small margin is an ambiguous attribution."""
        return (self.runner_up[1] - self.distance) if self.runner_up else float("inf")

    def report(self) -> str:
        if not self.receipt_ok:
            return f"REFUSED (provenance): {self.reason}"
        if not self.matched:
            near = f"{self.attributed_model} d={self.distance:.3f}" if self.ranked else "(empty registry)"
            return f"NOT ATTRIBUTED: nearest {near} — {self.reason}"
        s = f"ATTRIBUTED to {self.attributed_model} (d={self.distance:.3f}"
        if self.runner_up:
            s += f", margin over {self.runner_up[0]}: {self.margin:.3f}"
        return s + ")"


def attribute(
    candidate: LatentSignature,
    registry: SignatureRegistry,
    *,
    max_distance: float = 0.55,
    min_margin: float = 0.10,
    verify_receipt: bool = True,
) -> AttributionResult:
    """Attribute ``candidate`` to an enrolled model, or refuse.

    ``max_distance`` — the nearest enrolled signature must be at least this close
    (default 0.55: a genuine noisy re-measurement of a model shares most of its top
    features, an impostor shares almost none). ``min_margin`` — the nearest must clear
    the runner-up by this much, or the reading is ambiguous and refused.
    """
    if verify_receipt:
        ok, reason = verify_signature_receipt(candidate)
        if not ok:
            return AttributionResult(
                attributed_model=None, distance=float("inf"), matched=False,
                receipt_ok=False, reason=reason,
            )

    ranked = sorted(
        ((mid, signature_distance(candidate, ref)) for mid, ref in registry.signatures.items()),
        key=lambda t: t[1],
    )
    if not ranked:
        return AttributionResult(
            attributed_model=None, distance=float("inf"), matched=False,
            receipt_ok=True, ranked=[], reason="registry is empty; nothing to attribute against",
        )

    best_id, best_d = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    margin = (runner[1] - best_d) if runner else float("inf")

    within = best_d <= max_distance
    clears = margin >= min_margin
    matched = bool(within and clears)

    if matched:
        reason = "nearest signature within threshold and clear of the runner-up"
    elif not within:
        reason = (
            f"nearest distance {best_d:.3f} exceeds max_distance {max_distance:.2f}: "
            "no enrolled model matches (impostor/forgery or unknown model)"
        )
    else:
        reason = (
            f"margin {margin:.3f} below min_margin {min_margin:.2f}: the candidate is "
            f"nearly as close to {runner[0] if runner else '?'} — ambiguous, refused"
        )

    return AttributionResult(
        attributed_model=best_id if matched else best_id,
        distance=best_d,
        matched=matched,
        receipt_ok=True,
        runner_up=runner,
        ranked=ranked[:5],
        reason=reason,
    )
