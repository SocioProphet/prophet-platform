"""Theorems of the percolator core (fail-closed ordering, idempotent replay, both triggers) — proven
on fakes, no cluster. The library correctness (closure, isolation) is tested in tools/tests; here we
test the BATCH governance: receipt-before-checkpoint, empty-poll-no-receipt, envelope path."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make both the app package (src) and the shared library (repo root) importable.
_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "src"))
sys.path.insert(0, str(_APP.parents[1]))  # repo root -> tools.hellgraph_percolation

from hellgraph_percolator.percolator import GatewayError, Percolator  # noqa: E402


def _subgraph():
    return {
        "nodes": [
            {"id": "acme:A", "labels": ["dataset"], "properties": {"tenant_id": "acme", "op_set": "ingest"}},
            {"id": "acme:B", "labels": ["document"], "properties": {"tenant_id": "acme", "op_set": "ingest"}},
        ],
        "edgeList": [{"id": "e1", "label": "derives_from", "from": "acme:B", "to": "acme:A"}],
    }


class FakeGraph:
    def __init__(self, pages):
        self._pages = list(pages)

    def poll(self, since, limit):
        return self._pages.pop(0) if self._pages else {"events": [], "cursor": since, "version": since}

    def read_subgraph(self):
        return _subgraph()


class RecordingWriter:
    def __init__(self):
        self.requests = []

    def upsert(self, request):
        self.requests.append(request)


class FakeGateway:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def mint(self, **kw):
        self.calls.append(kw)
        if not self.ok:
            raise GatewayError("spine down")
        return {"id": "rcpt-1"}


def _percolator(pages, *, gateway_ok=True):
    return Percolator(graph=FakeGraph(pages), writer=RecordingWriter(), gateway=FakeGateway(gateway_ok))


def test_run_once_percolates_the_closure_then_seals_and_checkpoints():
    # THEOREM: a log event touching A re-materialises A AND its dependent B (the affected closure),
    # seals ONE receipt, and advances the cursor to the polled cut.
    p = _percolator([{"events": [{"seq": 1, "kind": "node", "id": "acme:A"}], "cursor": 1, "version": 1}])
    r = p.run_once(now="T")
    assert r.checkpointed and r.materialized == 2 and r.to_cursor == 1 and r.receipt_id == "rcpt-1"
    assert [req["nodes"][0]["node_id"] for req in p.writer.requests] == ["acme:A", "acme:B"]
    assert len(p.gateway.calls) == 1 and p.gateway.calls[0]["trigger"] == "log-tail"
    assert p.cursor == 1


def test_empty_poll_is_no_receipt_no_checkpoint():
    # THEOREM: receipts attest work, not heartbeats — an empty poll seals nothing and moves no cursor.
    p = _percolator([])
    r = p.run_once(now="T")
    assert not r.checkpointed and r.materialized == 0
    assert p.gateway.calls == [] and p.cursor == 0


def test_receipt_failure_aborts_before_the_checkpoint():
    # THEOREM (fail-closed): if the spine can't attest the batch, the cursor does NOT advance — the cut
    # is retried in full. The idempotent writes may have landed; re-running converges to the same graph.
    p = _percolator([{"events": [{"seq": 1, "kind": "node", "id": "acme:A"}], "cursor": 1, "version": 1}],
                    gateway_ok=False)
    with pytest.raises(GatewayError):
        p.run_once(now="T")
    assert p.cursor == 0  # NOT advanced past the unattested cut


def test_on_envelope_percolates_tenant_scoped_and_seals():
    # THEOREM: the webhook path percolates the change an exchange-envelope.v0 announces (its own tenant
    # only) and seals a receipt tagged as the envelope trigger; no cursor moves (not log-ordered).
    p = _percolator([])
    env = {"tenant_id": "acme", "asset_refs": ["acme:A"], "content_refs": ["globex:evil"]}
    r = p.on_envelope(env, now="T")
    assert r.checkpointed and r.materialized == 2 and r.trigger == "exchange-envelope"
    assert p.gateway.calls[0]["trigger"] == "exchange-envelope" and p.cursor == 0
    # globex:evil is cross-tenant → never seeded, so only acme's closure (A,B) is written
    assert all(req["tenant_id"] == "acme" for req in p.writer.requests)
