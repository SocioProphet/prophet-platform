"""Graph backend seam: in-memory (local-first default) vs hellgraph (opt-in).

The hellgraph tests use httpx.MockTransport — real client code paths, no live super-peer.
"""
import os

import httpx

from regis_acr_api.graph_backend import (
    HellGraphBackend,
    InMemoryBackend,
    get_backend,
    reset_backend,
)

DELTA = {
    "delta_id": "delta-1",
    "operations": [
        {"kind": "UPSERT_NODE", "node": {"node_id": "entity-x", "kind": "ENTITY_CLUSTER", "attrs": {}}}
    ],
}


# --- default backend selection is local-first ----------------------------------------------
def test_default_backend_is_in_memory(monkeypatch):
    monkeypatch.delenv("HELLGRAPH_SUPERPEER_URL", raising=False)
    reset_backend()
    try:
        assert get_backend().name == "in-memory"
    finally:
        reset_backend()


def test_env_opts_into_hellgraph(monkeypatch):
    monkeypatch.setenv("HELLGRAPH_SUPERPEER_URL", "http://superpeer.local:8080")
    reset_backend()
    try:
        assert get_backend().name == "hellgraph"
    finally:
        monkeypatch.delenv("HELLGRAPH_SUPERPEER_URL", raising=False)
        reset_backend()


# --- in-memory backend ----------------------------------------------------------------------
def test_in_memory_apply_get_health():
    b = InMemoryBackend()
    assert b.apply_delta(DELTA) == 1
    assert b.get("entity-x")["kind"] == "ENTITY_CLUSTER"
    assert b.get("missing") is None
    assert b.health() == {"backend": "in-memory", "nodes": 1}


# --- hellgraph backend: read via super-peer, write staged for sovereign participant ---------
def _mock_superpeer(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_hellgraph_health_passthrough():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/health"
        return httpx.Response(200, json={"ok": True, "nodes": 3, "writers": 2})

    b = HellGraphBackend("http://sp", client=_mock_superpeer(handler))
    h = b.health()
    assert h["backend"] == "hellgraph" and h["reachable"] is True
    assert h["superpeer"]["writers"] == 2


def test_hellgraph_read_from_materialized_view():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/query"
        body = req.read().decode()
        assert "gremlin" in body and "entity-x" in body  # by-id gremlin query
        atom = {"id": "entity-x", "labels": ["ENTITY_CLUSTER"], "properties": {"node_id": "entity-x", "kind": "ENTITY_CLUSTER"}}
        return httpx.Response(200, json={"results": {"values": [atom], "count": 1}})

    b = HellGraphBackend("http://sp", client=_mock_superpeer(handler))
    node = b.get("entity-x")
    assert node["node_id"] == "entity-x" and node["kind"] == "ENTITY_CLUSTER"


def test_hellgraph_write_stages_and_mirrors(tmp_path):
    outbox = tmp_path / "deltas.jsonl"

    def empty_view(req: httpx.Request) -> httpx.Response:
        # super-peer hasn't ingested the staged delta yet -> empty view
        return httpx.Response(200, json={"results": {"values": [], "count": 0}})

    b = HellGraphBackend("http://sp", client=_mock_superpeer(empty_view), outbox=str(outbox))
    assert b.apply_delta(DELTA) == 1
    # staged for the sovereign participant-writer (the ingest contract)
    assert outbox.read_text().strip() != ""
    assert len(b._staged) == 1
    # read-after-write falls back to the local mirror while the view is still empty
    assert b.get("entity-x")["node_id"] == "entity-x"


def test_hellgraph_unreachable_is_soft():
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    b = HellGraphBackend("http://sp", client=_mock_superpeer(boom))
    h = b.health()
    assert h["reachable"] is False and "error" in h  # opt-in plane down != service crash
    b.apply_delta(DELTA)
    assert b.get("entity-x")["node_id"] == "entity-x"  # mirror still serves the write
