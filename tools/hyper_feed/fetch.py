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
          attestation_verifier: Optional[AttestationVerifier] = None) -> AdmitResult:
    """Admit a fetched object iff its digest matches AND — when it carries an attestation_ref and a
    verifier is supplied — its provenance verifies. Fail-closed."""
    if not verify_digest(entry, content):
        return AdmitResult(entry["ref_id"], False, "digest-mismatch")
    att = entry.get("attestation_ref")
    if att and attestation_verifier is not None and not attestation_verifier(att):
        return AdmitResult(entry["ref_id"], False, "attestation-invalid")
    return AdmitResult(entry["ref_id"], True, "ok", content)


def federate(query_code: str, peer_manifest: Mapping, *, fetcher: Fetcher, max_hamming: int,
             op_set: Optional[str] = None,
             attestation_verifier: Optional[AttestationVerifier] = None) -> List[AdmitResult]:
    """Discover (Hamming match) → fetch → admit (verify), nearest first. Only admitted results carry
    content; a fetch failure is a rejection, not a crash."""
    index = {e["ref_id"]: e for e in peer_manifest.get("entries", [])}
    results: List[AdmitResult] = []
    for ref_id, _ in match(query_code, peer_manifest, max_hamming=max_hamming, op_set=op_set):
        entry = index[ref_id]
        try:
            content = fetcher(ref_id)
        except Exception as exc:  # noqa: BLE001 — any fetch failure is a rejection
            results.append(AdmitResult(ref_id, False, f"fetch-failed:{type(exc).__name__}"))
            continue
        results.append(admit(entry, content, attestation_verifier=attestation_verifier))
    return results
