from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import clickhouse_connect
import psycopg
from psycopg.rows import dict_row

# Health check results are cached for this many seconds to avoid creating
# a new DB connection on every K8s readiness probe (default period: 5 s).
_HEALTH_TTL: float = float(os.getenv("HEALTH_CACHE_TTL_S", "10"))

# { check_name -> (monotonic_timestamp, result_dict) }
_health_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_health_cache() -> None:
    """Evict all cached health results. Intended for test isolation."""
    _health_cache.clear()


def _cached_health(key: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    now = time.monotonic()
    entry = _health_cache.get(key)
    if entry is not None:
        ts, result = entry
        if now - ts < _HEALTH_TTL:
            return result
    result = fn()
    _health_cache[key] = (now, result)
    return result


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


def pg_execute(statements: list[tuple[str, tuple[Any, ...]]]) -> None:
    """Run one or more parameterized writes in a single transaction.

    Used by the head-to-head runner to persist eval_runs / trials / competitor_snapshots so a
    live reproduction shows up under /v1/competition/reproduced-vs-claimed. Always parameterized
    (never string-formatted) — same SQL-injection discipline as pg_fetch. Commits on success;
    psycopg rolls the whole transaction back if any statement raises.
    """
    with psycopg.connect(_postgres_dsn()) as conn:
        with conn.cursor() as cur:
            for sql, params in statements:
                cur.execute(sql, params)
        conn.commit()


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
    def _check() -> dict[str, Any]:
        try:
            rows = pg_fetch("select 1 as ok")
            return {"ok": len(rows) == 1}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": str(exc)}
    return _cached_health("postgres", _check)


def ch_health() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        try:
            rows = ch_query("select 1 as ok")
            return {"ok": len(rows) == 1}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": str(exc)}
    return _cached_health("clickhouse", _check)
