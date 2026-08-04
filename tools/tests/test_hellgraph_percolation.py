"""Theorems of the hellgraph percolation trigger (tools.hellgraph_percolation.percolation) and the
new graph-hyperedge.v0 contract. Deterministic."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.hellgraph_percolation import percolation as pc

ROOT = Path(__file__).resolve().parents[2]
HYPEREDGE_SCHEMA = ROOT / "contracts/crystal-atlas/schemas/graph-hyperedge.v0.schema.json"


class Rec:
    def __init__(self):
        self.requests = []

    def upsert(self, request):
        self.requests.append(request)


def _obj(oid, materializes=pc.NODE, tenant="t1", op_set="s1", derives_from=(), payload=None):
    return pc.CatalogObject(id=oid, materializes=materializes, tenant_id=tenant, op_set=op_set,
                            produced_by=f"script:{oid}", derives_from=tuple(derives_from),
                            payload=payload or {})


def _chain():
    # A <- B <- C  (C derives_from B, B derives_from A) plus an unrelated D
    c = pc.Catalog()
    c.add(_obj("A")).add(_obj("B", derives_from=["A"])).add(_obj("C", derives_from=["B"])).add(_obj("D"))
    return c


def test_closure_is_downstream_and_topological():
    # THEOREM: change A ⇒ closure {A,B,C}, each dependency before its dependent; D untouched.
    order = _chain().affected_closure(["A"])
    assert order == ["A", "B", "C"]
    assert "D" not in order


def test_percolation_is_incremental_downstream_only():
    # THEOREM: changing a mid-node re-materialises it + its dependents only, never upstream.
    order = _chain().affected_closure(["B"])
    assert order == ["B", "C"]  # A (upstream) is NOT re-materialised


def test_cycle_is_fail_closed():
    c = pc.Catalog()
    c.add(_obj("X", derives_from=["Y"])).add(_obj("Y", derives_from=["X"]))
    with pytest.raises(pc.CycleError):
        c.affected_closure(["X"])


def test_upserts_are_tenant_scoped_and_isolated():
    # THEOREM: every emitted graph-upsert-request carries its object's own tenant_id (isolation).
    c = pc.Catalog()
    c.add(_obj("A", tenant="alpha")).add(_obj("B", tenant="beta", derives_from=["A"]))
    rec = Rec()
    pc.percolate(c, ["A"], writer=rec, now="2026-08-04T00:00:00Z")
    assert [r["tenant_id"] for r in rec.requests] == ["alpha", "beta"]


def test_deterministic():
    c = _chain()
    r1, r2 = Rec(), Rec()
    a = pc.percolate(c, ["A"], writer=r1, now="T")
    b = pc.percolate(c, ["A"], writer=r2, now="T")
    assert a.order == b.order and r1.requests == r2.requests


def test_receipt_per_materialization():
    res = pc.percolate(_chain(), ["A"], writer=Rec(), now="2026-08-04T00:00:00Z")
    assert [r.object_id for r in res.receipts] == ["A", "B", "C"]
    assert all(r.materialized_at == "2026-08-04T00:00:00Z" and r.produced_by for r in res.receipts)


def test_hyperedge_materializes_into_hyperedges_array_with_op_set():
    # THEOREM: a hyperedge object emits into graph-upsert-request.v0 `hyperedges`, op_set stamped.
    body = {"hyperedge_id": "h1", "hyperedge_type": "argument",
            "members": [{"role": "claim", "node_id": "n1"}, {"role": "premise", "node_id": "n2"}]}
    c = pc.Catalog().add(_obj("h1", materializes=pc.HYPEREDGE, op_set="discourse", payload=body))
    rec = Rec()
    pc.percolate(c, ["h1"], writer=rec, now="T")
    (req,) = rec.requests
    assert "hyperedges" in req and req["tenant_id"] == "t1"
    assert req["hyperedges"][0]["op_set"] == "discourse"
    assert len(req["hyperedges"][0]["members"]) == 2


def test_graph_hyperedge_schema_accepts_valid_rejects_underspecified():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(HYPEREDGE_SCHEMA.read_text())
    valid = {
        "hyperedge_id": "he_001", "tenant_id": "t1", "op_set": "discourse",
        "hyperedge_type": "argument.support",
        "members": [{"role": "claim", "node_id": "n1"}, {"role": "premise", "node_id": "n2"}],
        "created_at": "2026-08-04T00:00:00Z", "updated_at": "2026-08-04T00:00:00Z",
    }
    jsonschema.validate(valid, schema)  # must not raise
    one_member = dict(valid, members=[{"role": "claim", "node_id": "n1"}])  # < 2 members
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(one_member, schema)
