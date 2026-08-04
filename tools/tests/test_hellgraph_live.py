"""Theorems of live percolation (tools.hellgraph_percolation.live) — the pure library made runnable:
a change (from the graph's log, or from an exchange-envelope.v0) rebuilds the catalog from LIVE graph
state and percolates the affected closure, writing scoped upserts. Injected reader + writer, no HTTP."""
from __future__ import annotations

from tools.hellgraph_percolation import live
from tools.hellgraph_percolation.percolation import Writer
from tools.hellgraph_percolation.writer_hellgraph import HellgraphServiceWriter


class RecordingWriter:
    """A Writer that records each graph-upsert-request.v0 it receives (the percolation actuation)."""
    def __init__(self) -> None:
        self.requests: list = []

    def upsert(self, request: dict) -> None:
        self.requests.append(request)


# A live hellgraph /api/graph/subgraph response: dataset A in op_set 'ingest', report B that
# derives_from A, and the reserved dependency edge B --derives_from--> A. Property-graph shape.
def _subgraph():
    return {
        "count": 2,
        "nodes": [
            {"id": "acme:A", "labels": ["dataset"], "properties": {"tenant_id": "acme", "op_set": "ingest", "name": "raw A"}},
            {"id": "acme:B", "labels": ["document"], "properties": {"tenant_id": "acme", "op_set": "ingest"}},
            {"id": "globex:C", "labels": ["dataset"], "properties": {"tenant_id": "globex", "op_set": "ingest"}},
        ],
        "edgeList": [
            {"id": "e1", "label": "derives_from", "from": "acme:B", "to": "acme:A"},
        ],
    }


def test_shape_adapter_inverts_the_property_graph_projection():
    # THEOREM: a hellgraph property-graph node round-trips to graph-node.v0 — first label is node_kind,
    # op_set is lifted back out of properties into attributes (its graph-node.v0 home).
    gn = live.property_node_to_graph_node(_subgraph()["nodes"][0], now="T")
    assert gn["node_id"] == "acme:A" and gn["node_kind"] == "dataset" and gn["tenant_id"] == "acme"
    assert gn["attributes"]["op_set"] == "ingest"
    ge = live.property_edge_to_graph_edge(_subgraph()["edgeList"][0])
    assert ge["edge_type"] == "derives_from" and ge["src"] == "acme:B" and ge["dst"] == "acme:A"


def test_catalog_reconstructs_the_dependency_graph_from_live_state():
    # THEOREM: graph_to_catalog rebuilds the derives_from dependency edges — B depends on A.
    cat = live.graph_to_catalog(_subgraph(), now="T")
    assert cat.objects["acme:B"].derives_from == ("acme:A",)
    assert cat.objects["acme:A"].op_set == "ingest"
    # a change to A percolates to its dependent B, in dependency order
    assert cat.affected_closure(["acme:A"]) == ["acme:A", "acme:B"]


def test_on_changed_percolates_the_live_closure():
    # THEOREM: a changed id (e.g. from a /api/graph/log tail) re-materialises A and everything that
    # derives from it, each a scoped graph-upsert-request.v0.
    rec = RecordingWriter()
    lp = live.LivePercolator(graph_reader=_subgraph, writer=rec)
    result = lp.on_changed(["acme:A"], now="T")
    assert result.order == ["acme:A", "acme:B"]
    assert [r["nodes"][0]["node_id"] for r in rec.requests] == ["acme:A", "acme:B"]


def test_on_envelope_percolates_tenant_scoped():
    # THEOREM: an exchange-envelope.v0 announcing a touched asset percolates ONLY its own tenant's
    # closure — a globex asset ref in an acme envelope can't trigger acme's rebuild, and vice versa.
    rec = RecordingWriter()
    lp = live.LivePercolator(graph_reader=_subgraph, writer=rec)
    env = {"tenant_id": "acme", "asset_refs": ["acme:A"], "content_refs": ["globex:C"]}
    result = lp.on_envelope(env, now="T")
    assert result.order == ["acme:A", "acme:B"]  # globex:C ignored (cross-tenant), acme:A's closure fires
    assert all(r["tenant_id"] == "acme" for r in rec.requests)


def test_end_to_end_op_set_reaches_the_wire_through_the_real_writer():
    # THEOREM: live percolation preserves isolation-by-default end to end — a node re-materialised from
    # live state lands WITH its op_set on the service POST body (the #1400 hardening, live).
    posts: list = []
    writer = HellgraphServiceWriter(post=lambda path, body: posts.append((path, body)), validate=True)
    live.LivePercolator(graph_reader=_subgraph, writer=writer).on_changed(["acme:A"], now="T")
    node_posts = [b for p, b in posts if p == "/api/graph/node"]
    assert node_posts and all(b["properties"]["op_set"] == "ingest" for b in node_posts)
    assert all(b["properties"]["tenant_id"] == "acme" for b in node_posts)


def test_changed_ids_from_log_covers_nodes_and_both_edge_endpoints():
    # THEOREM: a node log event contributes its id; an edge event contributes BOTH endpoints (a new
    # edge changes the dependency structure of both). De-duplicated.
    events = [
        {"seq": 1, "kind": "node", "id": "n1"},
        {"seq": 2, "kind": "edge", "label": "derives_from", "from": "n2", "to": "n1"},
    ]
    assert live.changed_ids_from_log(events) == ["n1", "n2"]
