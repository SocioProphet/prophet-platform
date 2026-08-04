"""Theorems of the self-hosted dependency graph (tools.hellgraph_percolation.catalog_loader):
`derives_from` / `produced_by` graph-edge.v0 edges ARE the dependency graph the trigger percolates."""
from __future__ import annotations

from tools.hellgraph_percolation import catalog_loader as cl
from tools.hellgraph_percolation import percolation as pc


def _node(nid, op_set="ingest", tenant="t1"):
    return {"node_id": nid, "tenant_id": tenant, "node_kind": "dataset", "display_name": nid,
            "attributes": {"op_set": op_set}, "created_at": "T", "updated_at": "T"}


def _edge(src, dst, edge_type, tenant="t1"):
    return {"edge_id": f"{src}->{dst}:{edge_type}", "tenant_id": tenant, "edge_type": edge_type,
            "src": src, "dst": dst, "created_at": "T", "updated_at": "T"}


class Rec:
    def __init__(self):
        self.requests = []

    def upsert(self, request):
        self.requests.append(request)


def test_derives_from_and_produced_by_build_the_dependency_graph():
    nodes = [_node("src.raw"), _node("derived.clean")]
    edges = [
        _edge("derived.clean", "src.raw", cl.DERIVES_FROM),        # clean derives from raw
        _edge("derived.clean", "script.cleaner", cl.PRODUCED_BY),  # clean produced by the cleaner
    ]
    cat = cl.load_catalog(nodes, edges)
    obj = cat.objects["derived.clean"]
    assert obj.derives_from == ("src.raw",) and obj.produced_by == "script.cleaner"
    assert obj.op_set == "ingest"
    # THEOREM: a change to the raw source percolates to re-materialise the derived dataset.
    assert cat.affected_closure(["src.raw"]) == ["src.raw", "derived.clean"]


def test_loaded_catalog_percolates_scoped_upserts():
    nodes = [_node("a"), _node("b"), _node("c")]
    edges = [_edge("b", "a", cl.DERIVES_FROM), _edge("c", "b", cl.DERIVES_FROM)]
    cat = cl.load_catalog(nodes, edges)
    rec = Rec()
    res = pc.percolate(cat, ["a"], writer=rec, now="T")
    assert res.order == ["a", "b", "c"]
    assert [r["tenant_id"] for r in rec.requests] == ["t1", "t1", "t1"]
    assert all("nodes" in r for r in rec.requests)  # each object materialises as a graph node


def test_domain_edges_are_not_dependencies():
    # THEOREM: a non-reserved edge type is a relation IN the graph, not a dependency OF it — it
    # never triggers a rebuild.
    nodes = [_node("post"), _node("author")]
    edges = [_edge("post", "author", "authored_by")]  # a domain relation, not derives_from
    cat = cl.load_catalog(nodes, edges)
    assert cat.objects["post"].derives_from == ()
    assert cat.affected_closure(["author"]) == ["author"]  # post does NOT rebuild
