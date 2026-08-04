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


def test_hyperedge_is_reified_losslessly_with_isolation_on_every_object():
    # THEOREM: a binary property-graph can't hold an N-ary relation, so the hyperedge reifies into a
    # node (labelled "hyperedge") + one role-labelled edge per member. Reification is LOSSLESS (the
    # node keeps confidence/claim_refs/evidence_refs) and ISOLATED (the node AND every role-edge carry
    # op_set + tenant_id) — a role-edge that dropped op_set would be invisible to an op_set-scoped read.
    rec = RecPost()
    he = {"hyperedge_id": "h1", "tenant_id": "t1", "op_set": "discourse", "hyperedge_type": "argument",
          "members": [{"role": "claim", "node_id": "c1"}, {"role": "premise", "node_id": "p1"}],
          "confidence": 0.9, "claim_refs": ["cl:1"], "evidence_refs": ["ev:1"],
          "created_at": "T", "updated_at": "T"}
    _writer(rec).upsert({"tenant_id": "t1", "hyperedges": [he]})
    assert len(rec.calls) == 3
    (np, nb), (ep1, eb1), (ep2, eb2) = rec.calls
    # reified node: labelled, isolated, and provenance-complete (lossless)
    assert np == "/api/graph/node" and nb["id"] == "h1" and "hyperedge" in nb["labels"]
    assert nb["properties"]["tenant_id"] == "t1" and nb["properties"]["op_set"] == "discourse"
    assert nb["properties"]["confidence"] == 0.9 and nb["properties"]["claim_refs"] == ["cl:1"]
    assert nb["properties"]["evidence_refs"] == ["ev:1"]
    # role edges: right shape AND carrying the relation's own isolation scope
    assert ep1 == "/api/graph/edge" and eb1["from"] == "h1" and eb1["to"] == "c1" and eb1["label"] == "claim"
    assert eb2["to"] == "p1" and eb2["label"] == "premise"
    for _, eb in (rec.calls[1], rec.calls[2]):
        assert eb["properties"]["op_set"] == "discourse" and eb["properties"]["tenant_id"] == "t1"
        assert eb["properties"]["reified_from"] == "h1"


def test_fail_closed_on_missing_tenant():
    rec = RecPost()
    with pytest.raises(ValueError):
        _writer(rec).upsert({"nodes": []})  # no tenant_id
    assert rec.calls == []  # nothing written


def test_fail_closed_on_claims_or_evidence_it_cannot_land():
    # THEOREM: the service boundary exposes no claims/evidence endpoint; rather than silently drop
    # them (losing provenance) the writer refuses fail-closed.
    rec = RecPost()
    with pytest.raises(ValueError):
        _writer(rec).upsert({"tenant_id": "t1", "claims": [{"claim_id": "c1"}]})
    assert rec.calls == []


def test_plugs_into_percolate_and_stamps_op_set_by_default():
    # THEOREM (isolation by default): a node whose payload carries NO op_set still lands WITH one —
    # percolate stamps the catalog object's op_set into attributes so no materialised object is ever
    # unlabelled. Regression guard: the write path previously dropped op_set for nodes/edges.
    rec = RecPost()
    cat = pc.Catalog().add(pc.CatalogObject(
        id="n1", materializes=pc.NODE, tenant_id="t1", op_set="s1", produced_by="script",
        payload={"node_id": "n1", "tenant_id": "t1", "node_kind": "dataset", "display_name": "n1",
                 "created_at": "T", "updated_at": "T"}))  # NOTE: payload has no attributes.op_set
    pc.percolate(cat, ["n1"], writer=_writer(rec), now="T")  # validate=True: the stamped op_set is present
    (path, body), = rec.calls
    assert path == "/api/graph/node"
    assert body["properties"]["op_set"] == "s1"     # the catalog's op_set reached the wire
    assert body["properties"]["tenant_id"] == "t1"
