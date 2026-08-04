"""Hyper Feed manifest — what a node publishes so peers federate WITHOUT trusting it or shipping raw
data. Each entry carries a compact semantic-hash `code` (cheap cross-node nearest-neighbour by Hamming),
a content `digest` (content-addressed fetch), and an `attestation_ref` (provenance verified via the twin
or an mcp-a2a AttestationBundle — referenced, not re-invented). Operational-set scoped.

A peer matches its query codes against a manifest by Hamming — no raw data moves, the codes alone
answer "who has something like this" — then verifies a fetched object by digest and checks provenance
by reference. Deterministic.
"""
from __future__ import annotations

import hashlib
from typing import List, Mapping, Optional, Sequence, Tuple

__all__ = ["hamming_hex", "content_digest", "build_manifest", "match", "verify_digest"]


def hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex-encoded codes (number of differing bits)."""
    if len(a) != len(b):
        raise ValueError("codes differ in length — incomparable")
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def content_digest(content: bytes) -> str:
    """A content-address used to verify a fetched object against the manifest."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


def build_manifest(node_id: str, tenant_id: str, entries: Sequence[Mapping], *,
                   manifest_id: Optional[str] = None, now: str = "") -> dict:
    """Assemble a hyper-feed-manifest.v0 from a node's entries (each: ref_id, op_set, code, digest,
    optionally attestation_ref)."""
    return {
        "manifest_id": manifest_id or f"hfm:{node_id}:{now}",
        "node_id": node_id,
        "tenant_id": tenant_id,
        "created_at": now,
        "entries": [dict(e) for e in entries],
    }


def match(query_code: str, manifest: Mapping, *, max_hamming: int,
          op_set: Optional[str] = None) -> List[Tuple[str, int]]:
    """A peer's query code → the manifest's (ref_id, hamming) within `max_hamming`, nearest first.
    If `op_set` is given, only entries in that set are considered (isolation). A code of a different
    length is incomparable and skipped, never a crash."""
    out: List[Tuple[str, int]] = []
    for e in manifest.get("entries", []):
        if op_set is not None and e.get("op_set") != op_set:
            continue
        try:
            d = hamming_hex(query_code, e["code"])
        except ValueError:
            continue
        if d <= max_hamming:
            out.append((e["ref_id"], d))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def verify_digest(entry: Mapping, content: bytes) -> bool:
    """A fetched object is trustworthy only if its content hashes to the manifest's digest."""
    return entry.get("digest") == content_digest(content)
