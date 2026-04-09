from __future__ import annotations

import app.db as db


class _DummyResult:
    column_names = ["ok"]
    result_rows = [(1,)]


class _DummyClient:
    def query(self, sql, parameters=None):
        return _DummyResult()


def test_clickhouse_dsn_config_is_respected(monkeypatch):
    seen = {}

    def fake_get_client(**kwargs):
        seen.update(kwargs)
        return _DummyClient()

    monkeypatch.setenv("CLICKHOUSE_DSN", "http://clickhouse:8123/default")
    monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
    monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
    monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
    monkeypatch.setattr(db.clickhouse_connect, "get_client", fake_get_client)

    rows = db.ch_query("select 1 as ok")

    assert rows == [{"ok": 1}]
    assert seen["host"] == "clickhouse"
    assert seen["port"] == 8123
    assert seen["database"] == "default"


def test_health_cache_serves_cached_result(monkeypatch):
    db.clear_health_cache()
    call_count = 0

    def fake_pg_fetch(_sql, _params=()):
        nonlocal call_count
        call_count += 1
        return [{"ok": 1}]

    monkeypatch.setattr(db, "pg_fetch", fake_pg_fetch)

    result1 = db.pg_health()
    result2 = db.pg_health()

    assert result1 == {"ok": True}
    assert result2 == {"ok": True}
    assert call_count == 1, "underlying fetch should only be called once within the TTL"


def test_health_cache_refreshes_after_ttl(monkeypatch):
    db.clear_health_cache()
    call_count = 0

    def fake_pg_fetch(_sql, _params=()):
        nonlocal call_count
        call_count += 1
        return [{"ok": 1}]

    monkeypatch.setattr(db, "pg_fetch", fake_pg_fetch)
    # Override TTL to zero so every call is a cache miss
    monkeypatch.setattr(db, "_HEALTH_TTL", 0.0)

    db.pg_health()
    db.pg_health()

    assert call_count == 2, "each call should hit the DB when TTL is zero"
