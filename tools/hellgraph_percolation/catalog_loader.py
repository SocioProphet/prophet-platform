"""Load a percolation Catalog from real hellgraph state — the dependency graph is **self-hosted**:
`derives_from` and `produced_by` are ordinary `graph-edge.v0` edges (reserved edge types), so the
whole graph becomes percolation-driven with no side catalog. A change to any node percolates through
its `derives_from` edges to re-materialise its dependents; `produced_by` names the script that does it.

Domain edges (any other `edge_type`) are relations *in* the graph, not dependencies *of* it, so the
loader ignores them when building the dependency graph — a "mentions" edge never triggers a rebuild.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Mapping

from tools.hellgraph_percolation.percolation import NODE, Catalog, CatalogObject

# Reserved edge types that describe the materialisation dependency graph (not domain relations):
DERIVES_FROM = "derives_from"   # src derives_from dst  ⇒  src depends on dst (dst is upstream)
PRODUCED_BY = "produced_by"     # src produced_by dst   ⇒  dst is the script/producer of src


def load_catalog(nodes: Iterable[Mapping], edges: Iterable[Mapping]) -> Catalog:
    """Build a percolation Catalog from graph-node.v0 objects + their `derives_from`/`produced_by`
    graph-edge.v0 edges. `op_set` is read from a node's attributes (default: "default")."""
    deps: Dict[str, List[str]] = defaultdict(list)
    producers: Dict[str, str] = {}
    for e in edges:
        et = e.get("edge_type")
        if et == DERIVES_FROM:
            deps[e["src"]].append(e["dst"])
        elif et == PRODUCED_BY:
            producers[e["src"]] = e["dst"]

    catalog = Catalog()
    for n in nodes:
        attrs = n.get("attributes") or {}
        catalog.add(CatalogObject(
            id=n["node_id"],
            materializes=NODE,
            tenant_id=n["tenant_id"],
            op_set=attrs.get("op_set", "default"),
            produced_by=producers.get(n["node_id"], ""),
            derives_from=tuple(deps.get(n["node_id"], ())),
            payload=dict(n),
        ))
    return catalog
