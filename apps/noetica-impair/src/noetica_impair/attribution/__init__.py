"""Zero-shot model attribution from latent signatures (prophet-workspace#76, item 4).

See :mod:`noetica_impair.attribution.signature` for the contract and the research
provenance. Public surface:

* :class:`~noetica_impair.attribution.signature.LatentSignature` — the record.
* :func:`~noetica_impair.attribution.signature.mint_signature` — bind it to the
  estate receipt chain.
* :func:`~noetica_impair.attribution.signature.signature_distance` — the metric.
* :class:`~noetica_impair.attribution.verify.SignatureRegistry`,
  :func:`~noetica_impair.attribution.verify.attribute`,
  :func:`~noetica_impair.attribution.verify.verify_signature_receipt` — the verifier.
"""

from __future__ import annotations

from .signature import (
    LatentSignature,
    concept_overlap,
    mint_signature,
    signature_distance,
)
from .verify import (
    AttributionResult,
    SignatureRegistry,
    attribute,
    verify_signature_receipt,
)

__all__ = [
    "LatentSignature",
    "mint_signature",
    "signature_distance",
    "concept_overlap",
    "SignatureRegistry",
    "AttributionResult",
    "attribute",
    "verify_signature_receipt",
]
