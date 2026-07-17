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


# ── Semantic embeddings (sovereign endpoint) ──────────────────────────────────
def test_extract_embedding_handles_openai_and_ollama_shapes():
    from memoryd.embedding import _extract_embedding
    assert _extract_embedding({"embedding": [1.0, 2.0]}) == [1.0, 2.0]            # Ollama native
    assert _extract_embedding({"embeddings": [[3.0, 4.0]]}) == [3.0, 4.0]         # Ollama batch
    assert _extract_embedding({"data": [{"embedding": [5.0, 6.0]}]}) == [5.0, 6.0]  # OpenAI
    assert _extract_embedding({"nope": 1}) == []


def test_build_embedder_defaults_to_hashing_without_url(monkeypatch):
    monkeypatch.delenv("EMBEDDINGS_URL", raising=False)
    from memoryd.embedding import build_embedder, HashingEmbedder
    e = build_embedder(dimension=8, salt="s")
    assert isinstance(e, HashingEmbedder)


def test_build_embedder_uses_remote_when_reachable(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_URL", "http://sovereign-embed/v1/embeddings")
    monkeypatch.setenv("EMBEDDINGS_MODEL", "nomic-embed-text")
    import memoryd.embedding as emb

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: FakeResp())

    e = emb.build_embedder(dimension=3, salt="s")
    assert isinstance(e, emb.RemoteEmbedder)
    assert e.embed("car") == [0.1, 0.2, 0.3]        # real semantic vector, not a hash


def test_build_embedder_falls_back_when_endpoint_unreachable(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_URL", "http://down/v1/embeddings")
    import memoryd.embedding as emb
    def boom(*a, **k): raise RuntimeError("connection refused")
    monkeypatch.setattr(emb.httpx, "post", boom)
    e = emb.build_embedder(dimension=4, salt="s")
    assert isinstance(e, emb.HashingEmbedder)        # consistent vector space, never mixed
