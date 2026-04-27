"""Deterministic receipt digest utilities.

This module intentionally does not sign receipts. It canonicalizes and digests
receipts so a gateway, release pipeline, or Lattice-admitted runtime boundary can
sign the digest later.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

Receipt = dict[str, Any]

CANONICALIZATION = "json-sort-keys-no-whitespace-v0"


def canonical_receipt(receipt: Receipt) -> str:
    """Return deterministic JSON for receipt digesting."""

    material = deepcopy(receipt)
    integrity = material.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("digest", None)
        integrity.pop("canonicalization", None)
    return json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def receipt_digest(receipt: Receipt) -> str:
    """Return sha256 digest string for a receipt."""

    encoded = canonical_receipt(receipt).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def attach_digest(receipt: Receipt) -> Receipt:
    """Return a receipt copy with deterministic digest metadata attached."""

    enriched = deepcopy(receipt)
    integrity = enriched.setdefault("integrity", {})
    integrity["canonicalization"] = CANONICALIZATION
    integrity["digest"] = receipt_digest(enriched)
    return enriched
