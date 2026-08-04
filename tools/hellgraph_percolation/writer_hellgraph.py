"""A real Writer — land graph-upsert-request.v0 on the hellgraph SERVICE boundary (not the fenced
engine). The service is a property graph: `POST /api/graph/node {id,labels,properties}` and
`POST /api/graph/edge {label,from,to,properties}`. So this translates the Crystal-Atlas shape into
those calls and REIFIES a hyperedge (which the binary service can't hold natively) as a node plus
one role-edge per member — the standard reification. Fail-closed: a structurally invalid upsert is
refused before any write. The HTTP poster is injectable, so the translation is fully testable with
no live engine.

Lane: this is an HTTP CLIENT to the service (svc/API); the Rust engine internals are untouched.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Callable, Mapping, Optional

Poster = Callable[[str, dict], None]  # (path, json_body) -> None


def _http_poster(base_url: str, token: Optional[str]) -> Poster:
    def post(path: str, body: dict) -> None:
        headers = {"content-type": "application/json"}
        if token:
            headers["authorization"] = f"Bearer {token}"  # graph:write scope when AUTH_ENFORCE=on
        req = urllib.request.Request(base_url.rstrip("/") + path, method="POST",
                                     data=json.dumps(body).encode("utf-8"), headers=headers)
        urllib.request.urlopen(req).read()
    return post


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _node_body(n: Mapping) -> dict:
    attrs = n.get("attributes") or {}
    return {
        "id": n["node_id"],
        "labels": [n["node_kind"], *n.get("aliases", [])],
        "properties": _clean({"tenant_id": n["tenant_id"], "display_name": n.get("display_name"),
                              "op_set": attrs.get("op_set"), "distribution_class": n.get("distribution_class"),
                              **attrs}),
    }


def _edge_body(e: Mapping) -> dict:
    return {
        "label": e["edge_type"], "from": e["src"], "to": e["dst"],
        "properties": _clean({"tenant_id": e["tenant_id"], "confidence": e.get("confidence"),
                              "claim_refs": e.get("claim_refs"), "evidence_refs": e.get("evidence_refs"),
                              **(e.get("attributes") or {})}),
    }


class HellgraphServiceWriter:
    """A percolation Writer that POSTs to the hellgraph service. Reifies hyperedges; fail-closed."""

    def __init__(self, *, base_url: str = "http://localhost:8090", token: Optional[str] = None,
                 post: Optional[Poster] = None, validate: bool = True) -> None:
        self._post = post or _http_poster(base_url, token)
        self._validate = validate

    def upsert(self, request: Mapping) -> None:
        if self._validate:
            _check(request)
        for node in request.get("nodes", []):
            self._post("/api/graph/node", _node_body(node))
        for edge in request.get("edges", []):
            self._post("/api/graph/edge", _edge_body(edge))
        for he in request.get("hyperedges", []):
            self._reify(he)

    def _reify(self, he: Mapping) -> None:
        # the hyperedge becomes a node carrying a "hyperedge" label ...
        self._post("/api/graph/node", {
            "id": he["hyperedge_id"],
            "labels": [he["hyperedge_type"], "hyperedge"],
            "properties": _clean({"tenant_id": he["tenant_id"], "op_set": he.get("op_set"),
                                  **(he.get("attributes") or {})}),
        })
        # ... and each roled member becomes a labelled edge out of it
        for m in he["members"]:
            self._post("/api/graph/edge", {
                "label": m["role"], "from": he["hyperedge_id"], "to": m["node_id"],
                "properties": {"member_role": m["role"], "reified_from": he["hyperedge_id"],
                               "tenant_id": he["tenant_id"]},
            })


def _check(request: Mapping) -> None:
    """Fail-closed structural validation before any write."""
    if not request.get("tenant_id"):
        raise ValueError("graph-upsert-request.v0 requires tenant_id")
    for n in request.get("nodes", []):
        if not all(n.get(k) for k in ("node_id", "tenant_id", "node_kind")):
            raise ValueError(f"invalid graph-node.v0: missing required field in {n!r}")
    for e in request.get("edges", []):
        if not all(e.get(k) for k in ("edge_id", "tenant_id", "edge_type", "src", "dst")):
            raise ValueError(f"invalid graph-edge.v0: missing required field in {e!r}")
    for h in request.get("hyperedges", []):
        if not all(h.get(k) for k in ("hyperedge_id", "tenant_id", "hyperedge_type")) or len(h.get("members", [])) < 2:
            raise ValueError(f"invalid graph-hyperedge.v0: {h!r}")
