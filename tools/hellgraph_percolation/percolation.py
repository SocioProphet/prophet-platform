"""Percolation trigger — the automatic materialisation loop for hellgraph. It ACTUATES
contract-percolation (declared across the estate, never yet actuated): a change percolates through
the catalog's dependency graph and re-materialises exactly the affected closure into hellgraph,
scoped by tenant + operational-set, each write receipted.

    sense (a change)  ->  plan (dependency closure, topological)  ->  actuate (scoped upsert)  ->  record (receipt)

Properties, by construction:
- **Incremental** — only the affected closure re-materialises, never the whole graph.
- **Bounded / governed** — the dependency graph must be a DAG; a cycle is fail-closed (CycleError),
  not an open loop.
- **Isolated by default** — every emitted write carries its object's own tenant_id AND op_set (op_set
  top-level on a hyperedge, in `attributes` on a node/edge), so the isolation label is ALWAYS present.
  Enforcing that boundary at read/write time is the graph service's responsibility (see the W2 "doors"
  governance layer); this trigger's job is to guarantee there is a label to enforce ON — never to emit
  an unlabelled object that a later reader cannot scope.
- **Engine-agnostic** — it emits `graph-upsert-request.v0` (the Crystal-Atlas MLN write interface)
  through a pluggable Writer; it never reaches inside the (fenced) graph engine.

Node/edge/hyperedge bodies are the producer's; this trigger owns the *envelope* and the *ordering*.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Protocol, Sequence

# What a catalog object materialises into, mapped to its graph-upsert-request.v0 array.
NODE, EDGE, HYPEREDGE = "node", "edge", "hyperedge"
_ARRAY = {NODE: "nodes", EDGE: "edges", HYPEREDGE: "hyperedges"}


class CycleError(ValueError):
    """The dependency graph must be a DAG; a cycle in the affected closure is fail-closed."""


@dataclass(frozen=True)
class CatalogObject:
    """A cataloged graph object + its materialisation dependencies."""

    id: str
    materializes: str                         # NODE | EDGE | HYPEREDGE
    tenant_id: str
    op_set: str                               # operational set / namespace — isolation by default
    produced_by: str                          # the script/producer that materialises this object
    derives_from: tuple = ()                  # upstream catalog object ids (dependency edges)
    payload: dict = field(default_factory=dict)  # the graph-*.v0 body to upsert


@dataclass(frozen=True)
class Receipt:
    """One materialisation, for the append-only audit / operational-exhaust trail."""

    object_id: str
    tenant_id: str
    op_set: str
    produced_by: str
    materialized_at: str


@dataclass(frozen=True)
class PercolationResult:
    order: List[str]
    receipts: List[Receipt]


class Writer(Protocol):
    """Anything that accepts a graph-upsert-request.v0 — the real engine client, or a recorder."""

    def upsert(self, request: dict) -> None:
        """Accept a graph-upsert-request.v0 and apply it (the engine client, or a recorder)."""


@dataclass
class Catalog:
    """The materialisation catalog: objects keyed by id, with their derives-from dependency edges."""

    objects: Dict[str, CatalogObject] = field(default_factory=dict)

    def add(self, obj: CatalogObject) -> "Catalog":
        self.objects[obj.id] = obj
        return self

    def _dependents(self) -> Dict[str, List[str]]:
        """Reverse dependency edges: object id -> the ids that derive_from it."""
        rev: Dict[str, List[str]] = {oid: [] for oid in self.objects}
        for oid, obj in self.objects.items():
            for up in obj.derives_from:
                if up in rev:
                    rev[up].append(oid)
        return rev

    def affected_closure(self, changed: Sequence[str]) -> List[str]:
        """The downstream closure of `changed` — the changed objects plus everything that
        (transitively) derives from them — in dependency (topological) order. Fail-closed on a
        cycle. Deterministic (ties broken by id)."""
        rev = self._dependents()
        seen: set = set()
        stack = [c for c in changed if c in self.objects]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack.extend(rev.get(x, ()))
        # Kahn topological sort within the closure; dependencies (derives_from) come first.
        indeg = {x: sum(1 for up in self.objects[x].derives_from if up in seen) for x in seen}
        ready = sorted(x for x in seen if indeg[x] == 0)
        order: List[str] = []
        while ready:
            x = ready.pop(0)
            order.append(x)
            for d in sorted(rev.get(x, ())):
                if d in seen:
                    indeg[d] -= 1
                    if indeg[d] == 0:
                        ready.append(d)
            ready.sort()
        if len(order) != len(seen):
            raise CycleError(f"cycle in affected closure: {sorted(seen - set(order))}")
        return order


def to_upsert_request(obj: CatalogObject) -> dict:
    """Wrap an object's body in a graph-upsert-request.v0 envelope, scoped to its tenant AND its
    operational set. op_set travels with EVERY object so isolation is by default, not best-effort:
    top-level on a hyperedge (graph-hyperedge.v0 has the field), and in `attributes.op_set` on a
    node/edge — graph-node/edge.v0 are additionalProperties:false, so the open `attributes` bag is
    op_set's home, where the writer and any op_set-scoped reader look for it. The attributes dict is
    copied, never mutated in place, so the catalog's payload is untouched."""
    body = dict(obj.payload)
    body.setdefault("tenant_id", obj.tenant_id)
    if obj.materializes == HYPEREDGE:
        body.setdefault("op_set", obj.op_set)
    else:
        attrs = dict(body.get("attributes") or {})
        attrs.setdefault("op_set", obj.op_set)
        body["attributes"] = attrs
    return {"tenant_id": obj.tenant_id, _ARRAY[obj.materializes]: [body]}


def percolate(catalog: Catalog, changed: Sequence[str], *, writer: Writer, now: str) -> PercolationResult:
    """Percolate `changed` through the catalog and materialise the affected closure in topological
    order, one scoped graph-upsert-request.v0 per object, each receipted."""
    order = catalog.affected_closure(changed)
    receipts: List[Receipt] = []
    for oid in order:
        obj = catalog.objects[oid]
        writer.upsert(to_upsert_request(obj))
        receipts.append(Receipt(oid, obj.tenant_id, obj.op_set, obj.produced_by, now))
    return PercolationResult(order=order, receipts=receipts)
