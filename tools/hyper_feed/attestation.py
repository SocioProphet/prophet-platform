"""Wire the mesh's fail-closed admission (tools.hyper_feed.fetch.admit) to the identity-twin (#1325).

A hyper-feed entry's `attestation_ref` encodes a twin VerifiableReference — the context, the Ed25519
`proof`, and the `verify_key` (procyber.semantic.vrf). The twin answers "is this provenance genuine?"
via `POST /verify {context, proof, verify_key} -> {verified}` (fail-closed: a forged proof verifies
false). `twin_attestation_verifier` returns exactly the `attestation_ref -> bool` callable admit expects,
so a fetched object is admitted only if BOTH its content content-addresses to the digest AND the twin
attests its reference.

Fail-closed throughout: an unparseable attestation, or an unreachable/erroring twin, verifies FALSE —
never admitted. encode/decode are pure (testable without a service); only `verify` touches HTTP.
"""
from __future__ import annotations

import base64
import json
import urllib.request
from typing import Callable, Optional

__all__ = ["encode_attestation", "decode_attestation", "twin_attestation_verifier"]

_PREFIX = "att:"
_FIELDS = ("context", "proof", "verify_key")


def encode_attestation(context: str, proof: str, verify_key: str) -> str:
    """Pack a twin VerifiableReference into a manifest `attestation_ref` string (url-safe base64 JSON)."""
    payload = json.dumps({"context": context, "proof": proof, "verify_key": verify_key})
    return _PREFIX + base64.urlsafe_b64encode(payload.encode()).decode()


def decode_attestation(attestation_ref: str) -> Optional[dict]:
    """Recover the {context, proof, verify_key} a manifest `attestation_ref` carries, or None if it is
    not a well-formed twin attestation."""
    if not attestation_ref.startswith(_PREFIX):
        return None
    try:
        ref = json.loads(base64.urlsafe_b64decode(attestation_ref[len(_PREFIX):].encode()))
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None
    return ref if isinstance(ref, dict) and all(k in ref for k in _FIELDS) else None


def twin_attestation_verifier(twin_url: str, *, timeout: float = 10.0) -> Callable[[str], bool]:
    """An `attestation_ref -> bool` verifier backed by the identity-twin's POST /verify. Fail-closed."""
    base = twin_url.rstrip("/")

    def verify(attestation_ref: str) -> bool:
        ref = decode_attestation(attestation_ref)
        if ref is None:
            return False  # not a parseable twin attestation ⇒ not genuine
        try:
            req = urllib.request.Request(
                base + "/verify", method="POST",
                data=json.dumps({k: ref[k] for k in _FIELDS}).encode("utf-8"),
                headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed internal URL
                return bool(json.loads(resp.read()).get("verified"))
        except Exception:  # noqa: BLE001 — an unreachable/erroring twin never attests (fail-closed)
            return False

    return verify
