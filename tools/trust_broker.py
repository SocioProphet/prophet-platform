#!/usr/bin/env python3
"""Trust broker (Workspace Control Plane, Phase 5 / D9, D16).

Verifies signed manifests and catalogs before remote discovery is allowed:
signature validity, freshness (expiry + optional max age), revocation, and — for
catalogs — the TUF-style delegation threshold. Every verification is recorded in
an append-only transparency log.

Signature verification is pluggable. The lab default (D16: trusted-lab stance)
implements a real keyed MAC (`hmac-blake2b`, stdlib only — no heavy deps).
Asymmetric algorithms (ed25519 / ecdsa-p256 / sigstore-keyless) require keys and
infrastructure; in the lab they report `verifier_unavailable` rather than
pretending to verify. Swap in a production verifier behind the same interface.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def canonical_signing_bytes(obj: dict[str, Any], *, exclude: tuple[str, ...]) -> bytes:
    """Deterministic bytes over an object with the signature field(s) excluded."""
    payload = {k: v for k, v in obj.items() if k not in exclude}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class KeyRegistry:
    """Maps a signer id to its lab MAC secret (bytes)."""

    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}

    def add(self, signer: str, secret: bytes) -> None:
        self._keys[signer] = secret

    def get(self, signer: str) -> Optional[bytes]:
        return self._keys.get(signer)


def mac_sign(payload: bytes, secret: bytes) -> str:
    """Lab signature: keyed blake2b MAC, hex."""
    return hashlib.blake2b(payload, key=secret).hexdigest()


def verify_signature(sig_block: dict[str, Any], payload: bytes, registry: KeyRegistry) -> tuple[bool, str]:
    """Verify one signature block against payload. Returns (ok, reason)."""
    algo = sig_block.get("algorithm")
    signer = sig_block.get("signer", "")
    sig = sig_block.get("signature", "")
    if algo == "hmac-blake2b":
        key = registry.get(signer)
        if key is None:
            return False, "unknown_signer"
        expected = mac_sign(payload, key)
        # Constant-time compare.
        ok = hmac.compare_digest(expected, sig)
        return ok, "ok" if ok else "bad_signature"
    # Asymmetric algorithms need production keys/infra.
    return False, "verifier_unavailable"


@dataclass
class TrustDecision:
    subject_id: str
    trusted: bool
    reasons: list[str] = field(default_factory=list)


class TrustBroker:
    """Verifies manifests/catalogs and records a transparency log."""

    def __init__(self, registry: KeyRegistry, *, max_age_seconds: Optional[int] = None) -> None:
        self.registry = registry
        self.max_age_seconds = max_age_seconds
        self.transparency_log: list[dict[str, Any]] = []

    def _record(self, decision: TrustDecision, now: str) -> None:
        self.transparency_log.append({
            "ts": now,
            "subject_id": decision.subject_id,
            "trusted": decision.trusted,
            "reasons": list(decision.reasons),
        })

    def _fresh(self, expiry: Optional[str], signed_at: Optional[str], now: str, reasons: list[str]) -> None:
        now_dt = _parse(now)
        if expiry and _parse(expiry) <= now_dt:
            reasons.append("expired")
        if self.max_age_seconds is not None and signed_at:
            if (now_dt - _parse(signed_at)).total_seconds() > self.max_age_seconds:
                reasons.append("stale")

    def verify_manifest(self, manifest: dict[str, Any], now: str) -> TrustDecision:
        subject_id = manifest.get("manifest_id", "?")
        reasons: list[str] = []
        sig = manifest.get("signature")
        if not sig:
            reasons.append("unsigned")
        else:
            payload = canonical_signing_bytes(manifest, exclude=("signature",))
            ok, why = verify_signature(sig, payload, self.registry)
            if not ok:
                reasons.append(why)
            self._fresh(manifest.get("expiry"), sig.get("signed_at"), now, reasons)
        rev = manifest.get("revocation") or {}
        if rev.get("revoked"):
            reasons.append("revoked")
        decision = TrustDecision(subject_id, not reasons, reasons)
        self._record(decision, now)
        return decision

    def verify_catalog(self, entry: dict[str, Any], now: str) -> TrustDecision:
        subject_id = entry.get("entry_id", "?")
        reasons: list[str] = []
        payload = canonical_signing_bytes(entry, exclude=("signatures",))
        valid = 0
        for sig in entry.get("signatures", []):
            ok, _ = verify_signature(sig, payload, self.registry)
            if ok:
                valid += 1
        threshold = (entry.get("delegation") or {}).get("threshold", 1)
        if valid < threshold:
            reasons.append(f"insufficient_signatures:{valid}<{threshold}")
        self._fresh(entry.get("expiry"), None, now, reasons)
        decision = TrustDecision(subject_id, not reasons, reasons)
        self._record(decision, now)
        return decision
