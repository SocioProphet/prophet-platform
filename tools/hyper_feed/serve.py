"""The SERVE half of the node-symmetric mesh — the other side of tools.hyper_feed.fetch's pull. A node
HOLDS objects (each with its semantic-hash `code`, `op_set`, content, and provenance attestation),
PUBLISHES a hyper-feed-manifest.v0 (the codes + digests peers match against, without shipping raw data),
and SERVES content-addressed fetch for the refs a peer matched.

Symmetry: every node runs BOTH halves — it `publish_manifest()` + `serve_fetch()` for peers, and uses
`fetch.federate()` to pull from theirs. The `code` comes from ⑤ `procyber.semantic.semantic_index`
(`codes_hex`) or `SemanticHasher` — so a node's index literally IS its federation advertisement. Nothing
here trusts a peer: admission (digest + attestation) is the fetcher's job (fetch.admit), never the server's.

Clean-room, deterministic, pure-Python. Theorems in tools/tests/test_hyper_feed_serve.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from tools.hyper_feed.manifest import build_manifest, content_digest

__all__ = ["Holding", "MeshNode"]


@dataclass(frozen=True)
class Holding:
    """One object this node holds and will serve: its ref, op_set, semantic-hash code, bytes, and the
    provenance attestation a peer will verify before admitting it."""

    ref_id: str
    op_set: str
    code: str  # hex semantic-hash (procyber.semantic.semantic_index.codes_hex / SemanticHasher)
    content: bytes
    attestation_ref: Optional[str] = None


@dataclass
class MeshNode:
    """A mesh node: hold objects, publish the manifest, serve fetch. Tenant- and op_set-scoped."""

    node_id: str
    tenant_id: str
    _holdings: Dict[str, Holding] = field(default_factory=dict, repr=False)

    def hold(self, ref_id: str, code: str, content: bytes, *,
             op_set: str = "default", attestation_ref: Optional[str] = None) -> "MeshNode":
        """Add (or replace) an object this node advertises + serves."""
        self._holdings[ref_id] = Holding(ref_id, op_set, code, content, attestation_ref)
        return self

    def __len__(self) -> int:
        return len(self._holdings)

    def publish_manifest(self, *, now: str = "") -> dict:
        """This node's hyper-feed-manifest.v0 — one entry per held object (ref_id, op_set, code, content
        digest, and attestation_ref when present). This is all a peer needs to match by Hamming; the raw
        content never leaves until a verified fetch."""
        entries = [
            {"ref_id": h.ref_id, "op_set": h.op_set, "code": h.code, "digest": content_digest(h.content),
             **({"attestation_ref": h.attestation_ref} if h.attestation_ref else {})}
            for h in self._holdings.values()
        ]
        return build_manifest(self.node_id, self.tenant_id, entries, now=now)

    def serve_fetch(self, ref_id: str) -> bytes:
        """Content-addressed fetch: the raw bytes for a ref a peer matched in the manifest. Fail-closed —
        an unknown ref raises (a peer cannot pull what this node does not hold), never returns empty."""
        h = self._holdings.get(ref_id)
        if h is None:
            raise KeyError(f"ref not held by {self.node_id}: {ref_id}")
        return h.content
