"""Materialise a discourse argument graph into hellgraph — the convergence of the semantic spine and
the graph. The argument-mining organ (procyber.discourse.argument_mining) emits an ArgumentGraph:
claims/premises (units) + support/attack (relations). This turns it into a `graph-upsert-request.v0`:

  - each unit  → a graph-node.v0 (node_kind "clause"; the argument role kept in attributes)
  - each relation → a graph-edge.v0 (edge_type = "support" | "attack")
  - each claim together with the premises that SUPPORT it → ONE N-ary graph-hyperedge.v0 (the
    argument as a relation, not three scattered binary edges)

It consumes the organ's `ArgumentGraph.to_dict()` shape (a plain dict), so there is no import
coupling to ProCybernetica — the discourse organ becomes a `produced_by` script for the percolation
trigger: a message arrives → the miner emits this → it materialises into hellgraph.
"""
from __future__ import annotations

from typing import Mapping


def materialize(argument_graph: Mapping, *, tenant_id: str, doc_id: str, op_set: str = "discourse",
                now: str = "") -> dict:
    """ArgumentGraph.to_dict() → graph-upsert-request.v0. `doc_id` is REQUIRED and namespaces every
    unit id, so two documents' claims/premises never collide in the shared graph — a bare "u0" from
    two different documents would otherwise merge into one node (and one "arg:u0" hyperedge). Empty
    doc_id is refused fail-closed rather than silently producing colliding ids."""
    if not doc_id:
        raise ValueError("materialize requires a non-empty doc_id — it namespaces node/hyperedge ids "
                         "to prevent cross-document collision in the shared graph")
    units = argument_graph.get("units", [])
    relations = argument_graph.get("relations", [])

    def nid(uid: str) -> str:
        return f"{doc_id}:{uid}"

    nodes = [{
        "node_id": nid(u["id"]),
        "tenant_id": tenant_id,
        "node_kind": "clause",  # a claim or premise is a clause in graph-node.v0's kinds
        "display_name": u["text"][:120],
        "attributes": {"op_set": op_set, "argument_role": u["role"]},
        "created_at": now, "updated_at": now,
    } for u in units]

    edges = [{
        "edge_id": f'{nid(r["source"])}->{nid(r["target"])}:{r["kind"]}',
        "tenant_id": tenant_id,
        "edge_type": r["kind"],
        "src": nid(r["source"]), "dst": nid(r["target"]),
        "attributes": {"op_set": op_set},
        "created_at": now, "updated_at": now,
    } for r in relations]

    # Each claim + the premises that support it → one N-ary "argument" hyperedge.
    supporters: dict = {}
    for r in relations:
        if r["kind"] == "support":
            supporters.setdefault(r["target"], []).append(r["source"])
    hyperedges = []
    for claim, premises in supporters.items():
        members = [{"role": "claim", "node_id": nid(claim)}]
        members += [{"role": "premise", "node_id": nid(p)} for p in premises]
        hyperedges.append({
            "hyperedge_id": f"arg:{nid(claim)}",
            "tenant_id": tenant_id, "op_set": op_set,
            "hyperedge_type": "argument",
            "members": members,
            "created_at": now, "updated_at": now,
        })

    request = {"tenant_id": tenant_id, "nodes": nodes, "edges": edges}
    if hyperedges:
        request["hyperedges"] = hyperedges
    return request
