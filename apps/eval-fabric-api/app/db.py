from __future__ import annotations

import os
from typing import Any

import clickhouse_connect
import psycopg
from psycopg.rows import dict_row

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://prophet:prophet@localhost:5432/prophet_platform")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")


def pg_fetch(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(POSTGRES_DSN) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def ch_query(sql: str) -> list[dict[str, Any]]:
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DATABASE,
    )
    result = client.query(sql)
    cols = list(result.column_names)
    return [dict(zip(cols, row)) for row in result.result_rows]
