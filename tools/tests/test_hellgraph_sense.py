"""Theorems of the sense edge (tools.hellgraph_percolation.sense): an exchange-envelope.v0 triggers
percolation of the downstream closure of the assets it touched, tenant-isolated and fail-safe."""
from __future__ import annotations

from tools.hellgraph_percolation import catalog_loader as cl
from tools.hellgraph_percolation import sense as sn


def _node(nid, tenant="t1"):
    return {"node_id": nid, "tenant_id": tenant, "node_kind": "dataset", "display_name": nid,
            "attributes": {"op_set": "ingest"}, "created_at": "T", "updated_at": "T"}


def _edge(src, dst, edge_type, tenant="t1"):
    return {"edge_id": f"{src}->{dst}", "tenant_id": tenant, "edge_type": edge_type,
            "src": src, "dst": dst, "created_at": "T", "updated_at": "T"}


class Rec:
    def __init__(self):
        self.requests = []

    def upsert(self, request):
        self.requests.append(request)


def test_changed_from_exchange_reads_asset_and_content_refs():
    env = {"asset_refs": ["a1", "a2"], "content_refs": ["c1", "a1"]}  # a1 duplicated
    assert sn.changed_from_exchange(env) == ["a1", "a2", "c1"]


def test_sense_percolates_downstream_of_the_exchanged_assets():
    nodes = [_node("raw"), _node("clean"), _node("report")]
    edges = [_edge("clean", "raw", cl.DERIVES_FROM), _edge("report", "clean", cl.DERIVES_FROM)]
    cat = cl.load_catalog(nodes, edges)
    env = {"exchange_id": "x1", "tenant_id": "t1", "asset_refs": ["raw"]}
    res = sn.sense(env, cat, writer=Rec(), now="T")
    assert res.order == ["raw", "clean", "report"]  # the whole downstream chain rebuilds


def test_sense_is_tenant_isolated():
    # A t1 object and a t2 object; a t1 exchange must not percolate the t2 object even if it names it.
    cat = cl.load_catalog([_node("t1obj", tenant="t1"), _node("t2obj", tenant="t2")], [])
    env = {"tenant_id": "t1", "asset_refs": ["t1obj", "t2obj"]}
    res = sn.sense(env, cat, writer=Rec(), now="T")
    assert res.order == ["t1obj"]


def test_sense_ignores_uncataloged_refs():
    cat = cl.load_catalog([_node("known")], [])
    env = {"tenant_id": "t1", "asset_refs": ["known", "ghost"]}
    res = sn.sense(env, cat, writer=Rec(), now="T")
    assert res.order == ["known"]  # ghost is skipped, not an error
