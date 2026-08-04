"""Live percolation — turn the pure percolation LIBRARY into a runnable trigger. Two entry points, one
core: a change signalled by the graph's own log (`on_changed`, the log-tail path) OR announced by an
estate exchange (`on_envelope`, the exchange-envelope.v0 path) percolates through the SAME catalog and
lands the same scoped upserts + receipts.

The catalog is rebuilt from LIVE graph state each trigger. The hellgraph service returns a PROPERTY
graph (`{id, labels[], properties}` nodes; `{label, from, to}` edges), not Crystal-Atlas graph-node.v0
shape — so `graph_to_catalog` INVERTS the writer's projection (`writer_hellgraph._node_body/_edge_body`)
back to the shape `catalog_loader` expects: a node's first label is its node_kind, `properties.tenant_id`
/`properties.op_set` come back out, and an edge's label is its edge_type — so the reserved dependency
edge types `derives_from`/`produced_by` survive the round-trip and the dependency graph reconstructs.

The graph reader and clock are injected, so the whole loop is testable with no HTTP and no engine.
"""
from __future__ import annotations

from typing import Callable, List, Mapping, Sequence

from tools.hellgraph_percolation.catalog_loader import load_catalog
from tools.hellgraph_percolation.percolation import Catalog, PercolationResult, Writer, percolate
from tools.hellgraph_percolation.sense import sense

# A reader of live graph state: returns the hellgraph-service /api/graph/subgraph response
# ({nodes: [{id, labels, properties}], edgeList: [{id, label, from, to}]}). Injected (HTTP, or a fake).
GraphReader = Callable[[], Mapping]

# graph-node.v0 / graph-edge.v0 fields that live in a first-class column, not the freeform attributes bag.
_RESERVED_NODE_PROPS = frozenset({"tenant_id", "op_set", "display_name", "name",
                                  "created_at", "updated_at", "distribution_class"})


def property_node_to_graph_node(n: Mapping, *, now: str = "") -> dict:
    """A hellgraph property-graph node (`{id, labels[], properties}`) → graph-node.v0 shape. The first
    label is the node_kind, the rest are aliases; tenant_id/op_set are lifted back out of properties
    (op_set lives in `attributes`, its graph-node.v0 home)."""
    props = dict(n.get("properties") or {})
    labels = list(n.get("labels") or [])
    attributes = {k: v for k, v in props.items() if k not in _RESERVED_NODE_PROPS}
    if props.get("op_set") is not None:
        attributes["op_set"] = props["op_set"]
    return {
        "node_id": n["id"],
        "tenant_id": props.get("tenant_id", ""),
        "node_kind": labels[0] if labels else "document",
        "display_name": props.get("display_name") or props.get("name") or n["id"],
        "aliases": labels[1:],
        "attributes": attributes,
        "created_at": props.get("created_at") or now,
        "updated_at": props.get("updated_at") or now,
    }


def property_edge_to_graph_edge(e: Mapping, *, now: str = "") -> dict:
    """A hellgraph property-graph edge (`{label, from, to}`) → graph-edge.v0 shape. The label is the
    edge_type — so `derives_from`/`produced_by` (the reserved dependency edges) round-trip and the
    dependency graph reconstructs from live state."""
    props = dict(e.get("properties") or {})
    return {
        "edge_id": e.get("id") or f'{e["from"]}->{e["to"]}:{e["label"]}',
        "tenant_id": props.get("tenant_id", ""),
        "edge_type": e["label"],
        "src": e["from"],
        "dst": e["to"],
        "attributes": {k: v for k, v in props.items() if k != "tenant_id"},
        "created_at": props.get("created_at") or now,
        "updated_at": props.get("updated_at") or now,
    }


def graph_to_catalog(subgraph: Mapping, *, now: str = "") -> Catalog:
    """A live hellgraph /api/graph/subgraph response → a percolation Catalog, inverting the property-graph
    projection back to the graph-node.v0/edge.v0 shape `catalog_loader` reads."""
    nodes = [property_node_to_graph_node(n, now=now) for n in subgraph.get("nodes", ())]
    edge_items = subgraph.get("edgeList") or subgraph.get("edges") or ()
    edges = [property_edge_to_graph_edge(e, now=now) for e in edge_items if isinstance(e, Mapping)]
    return load_catalog(nodes, edges)


class LivePercolator:
    """The runnable core: rebuild the catalog from live graph state, then percolate a change — whether
    the change arrived as a set of touched ids (the log-tail path) or as an exchange-envelope.v0 (the
    exchange path). The graph reader + writer are injected, so this is fully testable without HTTP."""

    def __init__(self, *, graph_reader: GraphReader, writer: Writer) -> None:
        self._read = graph_reader
        self._writer = writer

    def catalog(self, *, now: str = "") -> Catalog:
        """The dependency catalog as it stands in the live graph RIGHT NOW."""
        return graph_to_catalog(self._read(), now=now)

    def on_changed(self, changed_ids: Sequence[str], *, now: str) -> PercolationResult:
        """Percolate a set of changed node ids (e.g. derived from a /api/graph/log tail) through the
        live catalog. Ids absent from the catalog are ignored fail-safe (percolation.affected_closure)."""
        return percolate(self.catalog(now=now), list(changed_ids), writer=self._writer, now=now)

    def on_envelope(self, envelope: Mapping, *, now: str) -> PercolationResult:
        """Percolate the change an exchange-envelope.v0 announces (its asset_refs/content_refs), scoped
        to the envelope's own tenant. This is the automatic 'sense' edge, now driven by a real event."""
        return sense(envelope, self.catalog(now=now), writer=self._writer, now=now)


def changed_ids_from_log(events: Sequence[Mapping]) -> List[str]:
    """Derive the touched node ids from a /api/graph/log event page. A node event contributes its `id`;
    an edge event contributes BOTH endpoints (`from`/`to`) — a new edge changes the dependency structure
    of both. De-duplicated, order-preserving."""
    out: List[str] = []
    def add(x: object) -> None:
        if isinstance(x, str) and x and x not in out:
            out.append(x)
    for ev in events:
        add(ev.get("id"))
        add(ev.get("from"))
        add(ev.get("to"))
    return out
