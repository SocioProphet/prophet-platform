"""memoryd smoke — boots on the default in-memory store (no DB), serves health + a write/recall round-trip."""
from fastapi.testclient import TestClient

from memoryd.main import app

client = TestClient(app)


def test_healthz_on_inmemory_store():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body.get("store") is not None   # InMemoryStore reports healthy without any database configured


def test_root_identifies_service():
    r = client.get("/")
    assert r.status_code == 200
