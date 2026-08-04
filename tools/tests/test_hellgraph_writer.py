"""Theorems of the real Writer (tools.hellgraph_percolation.writer_hellgraph): translates
graph-upsert-request.v0 into hellgraph-service HTTP calls, reifies hyperedges, fail-closed."""
from __future__ import annotations

import pytest

from tools.hellgraph_percolation import percolation as pc
from tools.hellgraph_percolation import writer_hellgraph as wr


class RecPost:
    def __init__(self):
        self.calls = []

    def __call__(self, path, body):
        self.calls.append((path, body))


def _writer(rec, validate=True):
    return wr.HellgraphServiceWriter(post=rec, validate=validate)


def test_node_translates_to_service_node_upsert():
    rec = RecPost()
    _writer(rec).upsert({"tenant_id": "t1", "nodes": [
        {"node_id": "n1", "tenant_id": "t1", "node_kind": "dataset", "display_name": "raw",
         "attributes": {"op_set": "ingest"}, "created_at": "T", "updated_at": "T"}]})
    (path, body), = rec.calls
    assert path == "/api/graph/node"
    assert body["id"] == "n1" and body["labels"] == ["dataset"]
    assert body["properties"]["tenant_id"] == "t1" and body["properties"]["op_set"] == "ingest"


def test_edge_translates_to_service_edge_add():
    rec = RecPost()
    _writer(rec).upsert({"tenant_id": "t1", "edges": [
        {"edge_id": "e1", "tenant_id": "t1", "edge_type": "supports", "src": "a", "dst": "b",
         "created_at": "T", "updated_at": "T"}]})
    (path, body), = rec.calls
    assert path == "/api/graph/edge"
    assert body == {"label": "supports", "from": "a", "to": "b", "properties": {"tenant_id": "t1"}}


def test_hyperedge_is_reified_into_a_node_plus_role_edges():
    # THEOREM: a binary property-graph can't hold an N-ary relation, so the hyperedge reifies into
    # a node (labelled "hyperedge") + one role-labelled edge per member.
    rec = RecPost()
    he = {"hyperedge_id": "h1", "tenant_id": "t1", "op_set": "discourse", "hyperedge_type": "argument",
          "members": [{"role": "claim", "node_id": "c1"}, {"role": "premise", "node_id": "p1"}],
          "created_at": "T", "updated_at": "T"}
    _writer(rec).upsert({"tenant_id": "t1", "hyperedges": [he]})
    assert len(rec.calls) == 3
    (np, nb), (ep1, eb1), (ep2, eb2) = rec.calls
    assert np == "/api/graph/node" and nb["id"] == "h1" and "hyperedge" in nb["labels"]
    assert ep1 == "/api/graph/edge" and eb1["from"] == "h1" and eb1["to"] == "c1" and eb1["label"] == "claim"
    assert eb2["to"] == "p1" and eb2["label"] == "premise"


def test_fail_closed_on_missing_tenant():
    rec = RecPost()
    with pytest.raises(ValueError):
        _writer(rec).upsert({"nodes": []})  # no tenant_id
    assert rec.calls == []  # nothing written


def test_plugs_into_percolate_as_the_actuator():
    rec = RecPost()
    cat = pc.Catalog().add(pc.CatalogObject(
        id="n1", materializes=pc.NODE, tenant_id="t1", op_set="s1", produced_by="script",
        payload={"node_id": "n1", "tenant_id": "t1", "node_kind": "dataset", "display_name": "n1",
                 "created_at": "T", "updated_at": "T"}))
    pc.percolate(cat, ["n1"], writer=_writer(rec, validate=False), now="T")
    assert rec.calls and rec.calls[0][0] == "/api/graph/node"
