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


def _try_parse(ts: Any) -> Optional[datetime]:
    """Parse an attacker-controlled timestamp, returning None on anything invalid."""
    if not isinstance(ts, str):
        return None
    try:
        return _parse(ts)
    except (ValueError, TypeError):
        return None


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


# Algorithms with a real (production) verifier interface, pending keys/infra.
_KNOWN_ASYMMETRIC = {"ed25519", "ecdsa-p256", "sigstore-keyless"}


def signing_input(payload: bytes, signed_at: str) -> bytes:
    """The bytes a signature actually covers.

    `signed_at` is folded in so it is **authenticated** — otherwise it lives
    outside the signed payload and an attacker could replay an old valid
    signature with an edited `signed_at` to defeat max-age freshness.
    """
    return payload + b"\n:signed_at:" + signed_at.encode("utf-8")


def verify_signature(sig_block: dict[str, Any], payload: bytes, registry: KeyRegistry) -> tuple[bool, str]:
    """Verify one signature block against payload. Returns (ok, reason).

    Fail-closed on malformed/attacker-controlled input (non-dict block, non-string
    signer/signature/signed_at); distinguishes an *unsupported-in-lab* algorithm
    from an *unknown/typo* one. The signature covers `signed_at` (see
    [`signing_input`]).
    """
    if not isinstance(sig_block, dict):
        return False, "malformed_signature"
    algo = sig_block.get("algorithm")
    signer = sig_block.get("signer")
    sig = sig_block.get("signature")
    signed_at = sig_block.get("signed_at")
    # signer must be hashable/str (registry lookup), and sig/signed_at present strings.
    if not isinstance(signer, str) or not isinstance(sig, str) or not sig or not isinstance(signed_at, str):
        return False, "malformed_signature"
    if algo == "hmac-blake2b":
        key = registry.get(signer)
        if key is None:
            return False, "unknown_signer"
        ok = hmac.compare_digest(mac_sign(signing_input(payload, signed_at), key), sig)
        return ok, "ok" if ok else "bad_signature"
    if algo in _KNOWN_ASYMMETRIC:
        # Supported algorithm, but no production verifier wired in the lab stance.
        return False, "verifier_unavailable"
    # Typos / algorithms outside the declared enum are a distinct, diagnosable error.
    return False, "unknown_algorithm"


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
        now_dt = _parse(now)  # our own clock string; trusted format
        if expiry is not None:
            e = _try_parse(expiry)
            if e is None:
                reasons.append("bad_timestamp")  # fail closed on malformed input
            elif e <= now_dt:
                reasons.append("expired")
        if self.max_age_seconds is not None and signed_at is not None:
            s = _try_parse(signed_at)
            if s is None:
                reasons.append("bad_timestamp")
            elif (now_dt - s).total_seconds() > self.max_age_seconds:
                reasons.append("stale")

    def _sig_fresh(self, sig: Any, now_dt: datetime) -> bool:
        """Whether a single signature is within max_age (fail-closed)."""
        if self.max_age_seconds is None:
            return True
        signed_at = sig.get("signed_at") if isinstance(sig, dict) else None
        s = _try_parse(signed_at)
        return s is not None and (now_dt - s).total_seconds() <= self.max_age_seconds

    def verify_manifest(self, manifest: dict[str, Any], now: str) -> TrustDecision:
        subject_id = manifest.get("manifest_id", "?")
        reasons: list[str] = []
        sig = manifest.get("signature")
        if not sig:
            reasons.append("unsigned")
        elif not isinstance(sig, dict):
            reasons.append("malformed_signature")  # remote input; do not crash
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
        now_dt = _parse(now)
        sigs = entry.get("signatures", [])
        if not isinstance(sigs, list):
            sigs = []
        valid = 0
        for sig in sigs:
            ok, _ = verify_signature(sig, payload, self.registry)
            # A signature counts only if it verifies AND is within max_age.
            if ok and self._sig_fresh(sig, now_dt):
                valid += 1
        threshold = (entry.get("delegation") or {}).get("threshold", 1)
        if valid < threshold:
            reasons.append(f"insufficient_signatures:{valid}<{threshold}")
        self._fresh(entry.get("expiry"), None, now, reasons)
        decision = TrustDecision(subject_id, not reasons, reasons)
        self._record(decision, now)
        return decision
