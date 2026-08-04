"""Theorems of the discourse→hellgraph materializer (tools.hellgraph_percolation.argument_materializer):
an ArgumentGraph becomes graph-upsert-request.v0 — claims/premises→nodes, support/attack→edges, and
each claim+its-premises→one N-ary hyperedge. The discourse organ becomes a graph producer."""
from __future__ import annotations

from tools.hellgraph_percolation import argument_materializer as am
from tools.hellgraph_percolation import writer_hellgraph as wr


# The ArgumentGraph.to_dict() shape the organ (ProCybernetica #133) emits — reproduced here, no
# cross-repo import: "Cats are great because they purr. However, dogs are loyal."
ARG = {
    "units": [
        {"id": "u0", "text": "Cats are great", "role": "claim"},
        {"id": "u1", "text": "they purr", "role": "premise"},
        {"id": "u2", "text": "dogs are loyal", "role": "claim"},
    ],
    "relations": [
        {"source": "u1", "target": "u0", "kind": "support"},
        {"source": "u2", "target": "u0", "kind": "attack"},
    ],
}


def test_units_become_clause_nodes_with_role():
    req = am.materialize(ARG, tenant_id="t1", doc_id="msg1", now="T")
    assert {n["node_id"] for n in req["nodes"]} == {"msg1:u0", "msg1:u1", "msg1:u2"}
    assert all(n["node_kind"] == "clause" for n in req["nodes"])
    u0 = next(n for n in req["nodes"] if n["node_id"] == "msg1:u0")
    assert u0["attributes"]["argument_role"] == "claim" and u0["attributes"]["op_set"] == "discourse"
    assert u0["tenant_id"] == "t1"


def test_relations_become_typed_edges():
    req = am.materialize(ARG, tenant_id="t1", doc_id="msg1")
    kinds = {(e["edge_type"], e["src"], e["dst"]) for e in req["edges"]}
    assert ("support", "msg1:u1", "msg1:u0") in kinds
    assert ("attack", "msg1:u2", "msg1:u0") in kinds


def test_claim_with_premises_becomes_one_hyperedge():
    # THEOREM: the argument (a claim + its supporting premises) is ONE N-ary relation, not scattered edges.
    req = am.materialize(ARG, tenant_id="t1", doc_id="msg1")
    (he,) = req["hyperedges"]  # only u0 has a supporter
    assert he["hyperedge_type"] == "argument" and he["op_set"] == "discourse"
    roles = {(m["role"], m["node_id"]) for m in he["members"]}
    assert ("claim", "msg1:u0") in roles and ("premise", "msg1:u1") in roles
    assert "msg1:u2" not in {m["node_id"] for m in he["members"]}  # the attacker isn't a member


def test_output_is_a_valid_upsert_and_lands_via_the_writer():
    req = am.materialize(ARG, tenant_id="t1", doc_id="msg1", now="T")
    calls = []
    # validate=True ⇒ fail-closed structural check must pass, then translate to service calls.
    wr.HellgraphServiceWriter(post=lambda p, b: calls.append((p, b))).upsert(req)
    node_calls = [b for p, b in calls if p == "/api/graph/node"]
    assert len(node_calls) >= 4  # 3 clause nodes + 1 reified hyperedge node
    assert any(b["id"] == "arg:msg1:u0" and "hyperedge" in b["labels"] for b in node_calls)
