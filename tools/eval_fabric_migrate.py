#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import clickhouse_connect
import psycopg

ROOT = Path(__file__).resolve().parents[1]
PG_DIR = ROOT / "infra" / "datastores" / "postgres"
CH_DIR = ROOT / "infra" / "datastores" / "clickhouse"

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://prophet:prophet@localhost:5432/prophet_platform")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")


def sql_files(path: Path) -> list[Path]:
    return sorted(p for p in path.glob("*.sql") if p.name[:3].isdigit())


def ensure_pg_bookkeeping(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists schema_migrations (
              migration_name text primary key,
              applied_at timestamptz not null default now()
            )
            """
        )
    conn.commit()


def applied_pg(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("select migration_name from schema_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_pg(conn: psycopg.Connection, files: Iterable[Path]) -> list[str]:
    ensure_pg_bookkeeping(conn)
    already = applied_pg(conn)
    applied: list[str] = []
    for fp in files:
        if fp.name in already:
            continue
        sql = fp.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "insert into schema_migrations (migration_name) values (%s)",
                (fp.name,),
            )
        conn.commit()
        applied.append(fp.name)
    return applied


def ensure_ch_bookkeeping(client: clickhouse_connect.driver.client.Client) -> None:
    client.command(
        """
        create table if not exists schema_migrations (
          migration_name String,
          applied_at DateTime default now()
        )
        engine = ReplacingMergeTree
        order by migration_name
        """
    )


def applied_ch(client: clickhouse_connect.driver.client.Client) -> set[str]:
    result = client.query("select migration_name from schema_migrations")
    return {row[0] for row in result.result_rows}


def apply_ch(client: clickhouse_connect.driver.client.Client, files: Iterable[Path]) -> list[str]:
    ensure_ch_bookkeeping(client)
    already = applied_ch(client)
    applied: list[str] = []
    for fp in files:
        if fp.name in already:
            continue
        sql = fp.read_text(encoding="utf-8")
        client.command(sql)
        client.command(
            f"insert into schema_migrations (migration_name) values ('{fp.name}')"
        )
        applied.append(fp.name)
    return applied


def main() -> int:
    pg_files = sql_files(PG_DIR)
    ch_files = sql_files(CH_DIR)

    with psycopg.connect(POSTGRES_DSN) as pg_conn:
        pg_applied = apply_pg(pg_conn, pg_files)

    ch_client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DATABASE,
    )
    ch_applied = apply_ch(ch_client, ch_files)

    print("postgres_applied=", pg_applied)
    print("clickhouse_applied=", ch_applied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
