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
