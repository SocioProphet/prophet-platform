"""Node-to-node fetch — the pull half of Hyper Feed federation. Given a peer's manifest, a node
discovers matches by Hamming (manifest.match), fetches the raw objects, and ADMITS each only if it
verifies: the content content-addresses to the manifest's digest AND its provenance attestation
verifies. Fail-closed — a tampered object, an unverifiable attestation, or a failed fetch is rejected,
never admitted.

This is "trust nothing, verify everything" across the mesh: raw data moves only after the code-level
match, and only verified data is admitted. Fetcher + attestation verifier are injectable, so the whole
protocol is testable without a live peer or the real twin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Mapping, Optional

from tools.hyper_feed.manifest import match, verify_digest

Fetcher = Callable[[str], bytes]              # ref_id -> raw bytes (HTTP to the peer, or a mock)
AttestationVerifier = Callable[[str], bool]   # attestation_ref -> ok? (twin verify / mcp-a2a check)


@dataclass(frozen=True)
class AdmitResult:
    ref_id: str
    admitted: bool
    reason: str
    content: Optional[bytes] = None


def admit(entry: Mapping, content: bytes, *,
          attestation_verifier: Optional[AttestationVerifier] = None,
          require_attestation: bool = False) -> AdmitResult:
    """Admit a fetched object ONLY if its digest matches AND its provenance verifies. Fail-closed: the
    peer supplies BOTH the manifest digest and the bytes, so the digest only proves "the peer's bytes
    match the peer's own claim" — the attestation is the sole external trust anchor. So an attestation_ref
    that cannot be checked is REJECTED, never admitted:
      - no verifier supplied  -> reject (attestation-unverifiable)   [was: silently admitted]
      - verifier raises        -> reject (attestation-error)          [was: crashed the caller]
      - verifier returns False  -> reject (attestation-invalid)
    With `require_attestation`, an entry carrying NO attestation_ref is rejected too (strict mesh)."""
    if not verify_digest(entry, content):
        return AdmitResult(entry["ref_id"], False, "digest-mismatch")
    att = entry.get("attestation_ref")
    if att:
        if attestation_verifier is None:
            return AdmitResult(entry["ref_id"], False, "attestation-unverifiable")
        try:
            ok = attestation_verifier(att)
        except Exception as exc:  # noqa: BLE001 — a verifier failure is a rejection, never admission
            return AdmitResult(entry["ref_id"], False, f"attestation-error:{type(exc).__name__}")
        if not ok:
            return AdmitResult(entry["ref_id"], False, "attestation-invalid")
    elif require_attestation:
        return AdmitResult(entry["ref_id"], False, "attestation-missing")
    return AdmitResult(entry["ref_id"], True, "ok", content)


def federate(query_code: str, peer_manifest: Mapping, *, fetcher: Fetcher, max_hamming: int,
             op_set: Optional[str] = None,
             attestation_verifier: Optional[AttestationVerifier] = None,
             require_attestation: bool = False) -> List[AdmitResult]:
    """Discover (Hamming match) → fetch → admit (verify), nearest first. Only admitted results carry
    content; a fetch failure is a rejection, not a crash. Admission is fail-closed (see `admit`): with
    no verifier, an attested entry is rejected as unverifiable rather than trusted on digest alone."""
    index = {e["ref_id"]: e for e in peer_manifest.get("entries", [])}
    results: List[AdmitResult] = []
    for ref_id, _ in match(query_code, peer_manifest, max_hamming=max_hamming, op_set=op_set):
        entry = index[ref_id]
        try:
            content = fetcher(ref_id)
        except Exception as exc:  # noqa: BLE001 — any fetch failure is a rejection
            results.append(AdmitResult(ref_id, False, f"fetch-failed:{type(exc).__name__}"))
            continue
        results.append(admit(entry, content, attestation_verifier=attestation_verifier,
                             require_attestation=require_attestation))
    return results
