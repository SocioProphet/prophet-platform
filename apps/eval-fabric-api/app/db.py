from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import clickhouse_connect
import psycopg
from psycopg.rows import dict_row


def _postgres_dsn() -> str:
    return os.getenv("POSTGRES_DSN", "postgresql://prophet:prophet@localhost:5432/prophet_platform")


def _clickhouse_config() -> tuple[str, int, str]:
    dsn = os.getenv("CLICKHOUSE_DSN", "").strip()
    default_host = os.getenv("CLICKHOUSE_HOST", "localhost")
    default_port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    default_db = os.getenv("CLICKHOUSE_DATABASE", "default")

    if not dsn:
        return default_host, default_port, default_db

    parsed = urlparse(dsn)
    host = parsed.hostname or default_host
    port = parsed.port or default_port
    database = parsed.path.lstrip("/") or default_db
    return host, port, database


def pg_fetch(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(_postgres_dsn()) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def ch_query(sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    host, port, database = _clickhouse_config()
    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        database=database,
    )
    result = client.query(sql, parameters=parameters or {})
    cols = list(result.column_names)
    return [dict(zip(cols, row)) for row in result.result_rows]


def pg_health() -> dict[str, Any]:
    try:
        rows = pg_fetch("select 1 as ok")
        return {"ok": len(rows) == 1}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": str(exc)}


def ch_health() -> dict[str, Any]:
    try:
        rows = ch_query("select 1 as ok")
        return {"ok": len(rows) == 1}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": str(exc)}
