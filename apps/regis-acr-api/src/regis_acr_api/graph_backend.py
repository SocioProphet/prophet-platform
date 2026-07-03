"""Graph backing for the ER spine — local-first in-memory by default, hellgraph when opted-in.

Backend selection (opt-in, keeps the plane local-first):
  - `HELLGRAPH_SUPERPEER_URL` unset  -> InMemoryBackend (default; zero external dependency)
  - `HELLGRAPH_SUPERPEER_URL` set    -> HellGraphBackend (federated sovereign graph)

hellgraph's SuperPeer HTTP surface is READ + GOVERN only (`GET /health`, `GET /cut`,
`POST /query`, `POST /admit`) — by design it "cannot forge or rewrite": sovereign writes go
through a participant's own Hypercore log, never an HTTP write to the index. So the hellgraph
backend:
  - READS from the super-peer's materialized view via `POST /query` (Gremlin), and
  - STAGES writes as graph_delta records in an outbox — the ingest contract a hellgraph
    sovereign participant-writer (Hypercore append) consumes. It never POSTs writes to the
    super-peer, which would violate the sovereignty model.

Node <-> hellgraph atom mapping: regis node_id -> atom id (+ a `node_id` property for lookup),
regis kind -> atom label, and the regis node body is carried in atom properties.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import httpx


@runtime_checkable
class GraphBackend(Protocol):
    name: str

    def apply_delta(self, delta: Dict[str, Any]) -> int: ...
    def get(self, node_id: str) -> Optional[Dict[str, Any]]: ...
    def health(self) -> Dict[str, Any]: ...


def _nodes_of(delta: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [op["node"] for op in delta.get("operations", []) if op.get("kind") == "UPSERT_NODE" and "node" in op]


class InMemoryBackend:
    """Default local-first backing. Rebuildable, in-process, no external dependency."""

    name = "in-memory"

    def __init__(self) -> None:
        self._nodes: Dict[str, Dict[str, Any]] = {}

    def apply_delta(self, delta: Dict[str, Any]) -> int:
        applied = 0
        for node in _nodes_of(delta):
            self._nodes[node["node_id"]] = node
            applied += 1
        return applied

    def get(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._nodes.get(node_id)

    def health(self) -> Dict[str, Any]:
        return {"backend": self.name, "nodes": len(self._nodes)}


def _gremlin_by_id(node_id: str) -> str:
    # node_id carried as an atom property; escape single quotes defensively.
    safe = node_id.replace("'", "\\'")
    return f"g.V().has('node_id', '{safe}')"


def _atom_to_node(atom: Any) -> Optional[Dict[str, Any]]:
    """Map a hellgraph atom {id,labels,properties} back to a regis node. The regis body rides in
    properties; if that isn't present yet (writer slice not landed), return the raw atom."""
    if isinstance(atom, dict):
        props = atom.get("properties")
        if isinstance(props, dict) and "node_id" in props:
            return props
        return atom
    return None


class HellGraphBackend:
    """Reads the federated sovereign graph via the super-peer; stages writes for a participant-writer."""

    name = "hellgraph"

    def __init__(self, base_url: str, client: Optional[httpx.Client] = None, outbox: Optional[str] = None) -> None:
        self._url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=5.0)
        self._outbox = outbox  # optional durable append-only path for the ingest contract
        self._staged: List[Dict[str, Any]] = []
        self._mirror: Dict[str, Dict[str, Any]] = {}  # in-process read-after-write mirror

    def apply_delta(self, delta: Dict[str, Any]) -> int:
        # stage for the sovereign participant-writer; the super-peer is read+govern only.
        self._staged.append(delta)
        if self._outbox:
            with open(self._outbox, "a", encoding="utf-8") as f:
                f.write(json.dumps(delta) + "\n")
        applied = 0
        for node in _nodes_of(delta):
            self._mirror[node["node_id"]] = node
            applied += 1
        return applied

    def get(self, node_id: str) -> Optional[Dict[str, Any]]:
        # prefer hellgraph's materialized view; fall back to the local write mirror.
        try:
            r = self._client.post(
                f"{self._url}/query", json={"lang": "gremlin", "query": _gremlin_by_id(node_id)}
            )
            if r.status_code == 200:
                values = ((r.json() or {}).get("results") or {}).get("values") or []
                if values:
                    node = _atom_to_node(values[0])
                    if node:
                        return node
        except Exception:
            pass  # federated read is best-effort; fall through to the mirror
        return self._mirror.get(node_id)

    def health(self) -> Dict[str, Any]:
        base: Dict[str, Any] = {"backend": self.name, "superpeer_url": self._url, "staged_deltas": len(self._staged)}
        try:
            r = self._client.get(f"{self._url}/health")
            base["reachable"] = r.status_code == 200
            base["superpeer"] = r.json()
        except Exception as e:  # opt-in cloud plane may be down; don't crash the service
            base["reachable"] = False
            base["error"] = str(e)
        return base


_BACKEND: Optional[GraphBackend] = None


def get_backend() -> GraphBackend:
    global _BACKEND
    if _BACKEND is None:
        url = os.environ.get("HELLGRAPH_SUPERPEER_URL")
        _BACKEND = (
            HellGraphBackend(url, outbox=os.environ.get("HELLGRAPH_DELTA_OUTBOX"))
            if url
            else InMemoryBackend()
        )
    return _BACKEND


def reset_backend() -> None:
    """Test/hot-reload hook — clears the memoized backend so env changes take effect."""
    global _BACKEND
    _BACKEND = None
