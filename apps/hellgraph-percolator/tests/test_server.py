"""Theorems of the HTTP shell — /healthz answers honestly, and POST /percolate (the exchange-envelope.v0
webhook) percolates + seals fail-closed. Loop disabled (PERCOLATOR_LOOP=off); a fake percolator is
injected so nothing touches a real cluster."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["PERCOLATOR_LOOP"] = "off"
_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "src"))
sys.path.insert(0, str(_APP.parents[1]))  # repo root -> tools.hellgraph_percolation

from fastapi.testclient import TestClient  # noqa: E402

from hellgraph_percolator import server  # noqa: E402
from hellgraph_percolator.percolator import GatewayError, Percolator  # noqa: E402


def _subgraph():
    return {
        "nodes": [
            {"id": "acme:A", "labels": ["dataset"], "properties": {"tenant_id": "acme", "op_set": "ingest"}},
            {"id": "acme:B", "labels": ["document"], "properties": {"tenant_id": "acme", "op_set": "ingest"}},
        ],
        "edgeList": [{"id": "e1", "label": "derives_from", "from": "acme:B", "to": "acme:A"}],
    }


class _Graph:
    def poll(self, since, limit):
        return {"events": [], "cursor": since, "version": since}

    def read_subgraph(self):
        return _subgraph()


class _Writer:
    def __init__(self):
        self.requests = []

    def upsert(self, request):
        self.requests.append(request)


class _Gateway:
    def __init__(self, ok=True):
        self.ok = ok

    def mint(self, **kw):
        if not self.ok:
            raise GatewayError("spine down")
        return {"id": "rcpt-1"}


def _client(*, gateway_ok=True):
    fake = Percolator(graph=_Graph(), writer=_Writer(), gateway=_Gateway(gateway_ok))
    server.build_percolator = lambda: fake  # injected before lifespan runs
    return TestClient(server.app)


def test_healthz_is_honest_and_200():
    with _client() as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["service"] == "hellgraph-percolator"
        assert "last_cursor" in body and "receipts" in body


def test_percolate_webhook_percolates_and_returns_a_receipt():
    with _client() as c:
        r = c.post("/percolate", json={"tenant_id": "acme", "asset_refs": ["acme:A"]})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["trigger"] == "exchange-envelope"
        assert body["materialized"] == 2 and body["receipt_id"] == "rcpt-1"  # A + its dependent B


def test_percolate_requires_tenant_id():
    with _client() as c:
        r = c.post("/percolate", json={"asset_refs": ["acme:A"]})
        assert r.status_code == 400 and r.json()["ok"] is False


def test_percolate_is_fail_closed_on_receipt_failure():
    # THEOREM: a spine that can't attest → 502, not a silent success. The caller safely re-POSTs.
    with _client(gateway_ok=False) as c:
        r = c.post("/percolate", json={"tenant_id": "acme", "asset_refs": ["acme:A"]})
        assert r.status_code == 502 and "receipt refused" in r.json()["error"]
