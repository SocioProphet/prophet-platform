"""arcticdb-gateway tests — real embedded ArcticDB over a tmpdir LMDB (no mocks).

Each test gets a fresh LMDB under pytest's tmp_path, exercising the exact storage engine the
image ships (arcticdb==4.4.3): write/version semantics, time-travel reads, and the version
catalog are all asserted against the real library, not a fake.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from arcticdb_gateway.server import create_app


TEST_TOKEN = "test-write-token"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # /v1/write is fail-closed: configure a token and present it, so these tests
    # exercise the AUTHORIZED path. The refusals get their own tests below.
    monkeypatch.setenv("GATEWAY_TOKEN", TEST_TOKEN)
    app = create_app(f"lmdb://{tmp_path}/arctic?map_size=256MB")  # small map for tests
    with TestClient(app, headers={"Authorization": f"Bearer {TEST_TOKEN}"}) as c:
        yield c


@pytest.fixture()
def unauthed_client(tmp_path, monkeypatch):
    """Same app, no token configured and none presented."""
    monkeypatch.delenv("GATEWAY_TOKEN", raising=False)
    app = create_app(f"lmdb://{tmp_path}/arctic?map_size=256MB")
    with TestClient(app) as c:
        yield c


def test_healthz_reports_backend(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "arcticdb-gateway"
    assert body["backend"].startswith("lmdb://")
    assert body["libraries"] == 0


def test_write_read_roundtrip_with_datetime_index(client):
    payload = {
        "library": "prices",
        "symbol": "ASX.GYG",
        "data": {"close": [10.5, 11.25, 10.9], "volume": [100, 250, 175]},
        "index": ["2026-07-01T00:00:00", "2026-07-02T00:00:00", "2026-07-03T00:00:00"],
        "metadata": {"source": "test-fixture"},
    }
    w = client.post("/v1/write", json=payload)
    assert w.status_code == 200, w.text
    assert w.json() == {
        "library": "prices",
        "symbol": "ASX.GYG",
        "version": 0,
        "rows": 3,
        "columns": ["close", "volume"],
    }

    r = client.get("/v1/read", params={"library": "prices", "symbol": "ASX.GYG"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 0
    assert body["data"]["close"] == [10.5, 11.25, 10.9]
    assert body["data"]["volume"] == [100, 250, 175]
    assert body["index"] == ["2026-07-01T00:00:00", "2026-07-02T00:00:00", "2026-07-03T00:00:00"]
    assert body["metadata"] == {"source": "test-fixture"}


def test_versioning_and_time_travel(client):
    base = {"library": "ts", "symbol": "series"}
    v0 = client.post("/v1/write", json={**base, "data": {"x": [1, 2]}})
    v1 = client.post("/v1/write", json={**base, "data": {"x": [3, 4, 5]}})
    assert (v0.json()["version"], v1.json()["version"]) == (0, 1)

    latest = client.get("/v1/read", params={"library": "ts", "symbol": "series"}).json()
    assert latest["version"] == 1
    assert latest["data"]["x"] == [3, 4, 5]

    time_travel = client.get(
        "/v1/read", params={"library": "ts", "symbol": "series", "as_of": 0}
    ).json()
    assert time_travel["version"] == 0
    assert time_travel["data"]["x"] == [1, 2]

    vs = client.get("/v1/versions", params={"library": "ts"})
    assert vs.status_code == 200
    versions = vs.json()["versions"]
    assert [(v["symbol"], v["version"]) for v in versions] == [("series", 1), ("series", 0)]
    assert all(v["deleted"] is False and v["date"] is not None for v in versions)


def test_versions_filtered_by_symbol(client):
    client.post("/v1/write", json={"library": "lib", "symbol": "a", "data": {"x": [1]}})
    client.post("/v1/write", json={"library": "lib", "symbol": "b", "data": {"x": [2]}})
    only_a = client.get("/v1/versions", params={"library": "lib", "symbol": "a"}).json()["versions"]
    assert [(v["symbol"], v["version"]) for v in only_a] == [("a", 0)]


def test_missing_symbol_and_library_are_404(client):
    client.post("/v1/write", json={"library": "exists", "symbol": "s", "data": {"x": [1]}})
    assert client.get("/v1/read", params={"library": "exists", "symbol": "nope"}).status_code == 404
    assert client.get("/v1/read", params={"library": "ghost", "symbol": "s"}).status_code == 404
    assert client.get("/v1/versions", params={"library": "ghost"}).status_code == 404
    # a version that never existed time-travels to a 404, not a 500
    assert (
        client.get(
            "/v1/read", params={"library": "exists", "symbol": "s", "as_of": 99}
        ).status_code
        == 404
    )


def test_write_validation_is_400(client):
    mismatched = {"library": "l", "symbol": "s", "data": {"a": [1, 2], "b": [1]}}
    assert client.post("/v1/write", json=mismatched).status_code == 400
    empty = {"library": "l", "symbol": "s", "data": {}}
    assert client.post("/v1/write", json=empty).status_code == 400
    bad_index = {"library": "l", "symbol": "s", "data": {"a": [1]}, "index": ["not-a-time"]}
    assert client.post("/v1/write", json=bad_index).status_code == 400
    wrong_index_len = {"library": "l", "symbol": "s", "data": {"a": [1]}, "index": []}
    assert client.post("/v1/write", json=wrong_index_len).status_code == 400


def test_writes_persist_across_store_handles(tmp_path):
    """Durability: a second app instance over the same LMDB path sees the first one's writes."""
    uri = f"lmdb://{tmp_path}/arctic?map_size=256MB"
    with TestClient(create_app(uri)) as c1:
        c1.post("/v1/write", json={"library": "dur", "symbol": "s", "data": {"x": [7]}})
    with TestClient(create_app(uri)) as c2:
        got = c2.get("/v1/read", params={"library": "dur", "symbol": "s"})
        assert got.status_code == 200
        assert got.json()["data"]["x"] == [7]


# /v1/write mutated the LMDB-backed store with no authentication at all — anything that
# could reach the pod could write versioned artifacts into it. These are the refusals;
# a write gate never observed refusing is indistinguishable from no gate.


def test_write_refuses_when_no_token_is_configured(unauthed_client):
    # Fail-closed: an unconfigured gateway refuses rather than serving open.
    r = unauthed_client.post("/v1/write", json={"library": "l", "symbol": "s", "data": {"x": [1]}})
    assert r.status_code == 503
    assert "fail-closed" in r.json()["detail"]


def test_write_refuses_a_wrong_token(client):
    r = client.post(
        "/v1/write",
        json={"library": "l", "symbol": "s", "data": {"x": [1]}},
        headers={"Authorization": "Bearer not-the-token"},
    )
    assert r.status_code == 401


def test_write_refuses_a_missing_header_when_a_token_is_configured(client):
    r = client.post(
        "/v1/write",
        json={"library": "l", "symbol": "s", "data": {"x": [1]}},
        headers={"Authorization": ""},
    )
    assert r.status_code == 401


def test_write_accepts_the_configured_token(client):
    r = client.post("/v1/write", json={"library": "l", "symbol": "s", "data": {"x": [1]}})
    assert r.status_code == 200


def test_only_the_write_route_is_token_gated(tmp_path):
    """Structural: the auth dependency is attached to /v1/write and to nothing else.

    Asserted against the route table rather than by issuing requests, so it holds
    regardless of whether the storage backend can be opened in this environment.
    The asymmetry is deliberate — this closes the MUTATION path. A read that cannot
    cite a token is still a read; a write that cannot is an anonymous mutation.
    """
    from arcticdb_gateway.server import require_token

    app = create_app(f"lmdb://{tmp_path}/arctic?map_size=256MB")
    gated = {
        r.path
        for r in app.routes
        if any(d.call is require_token for d in getattr(getattr(r, "dependant", None), "dependencies", []))
    }
    assert gated == {"/v1/write"}, f"expected only /v1/write to be gated, got {gated}"
