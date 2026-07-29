"""The three doors the materializer talks through — all injectable, so unit tests run on
fakes and the loop's correctness (checkpoint ordering, idempotency, fail-closed receipts)
is proven without a cluster.

- HellGraphClient    → hellgraph-service GET /api/graph/log (THE log; pht.md commitment 1)
- ClickHouseClient   → ClickHouse's plain HTTP interface (:8123). No driver dependency:
                       INSERT ... FORMAT JSONEachRow over httpx is the whole protocol.
- GatewayClient      → compute-gateway POST /v1/compute kind=materialize (THE receipt
                       spine; pht.md commitment 3 — never a parallel receipt lineage).
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))


class HellGraphClient:
    """Log-tail reader. `poll` is since-EXCLUSIVE and returns the endpoint's contract
    verbatim: {events: [...], cursor: <max seq in page | since>, version: <logical clock>}."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def poll(self, since: int, limit: int) -> dict[str, Any]:
        r = httpx.get(f"{self.base_url}/api/graph/log",
                      params={"since": since, "limit": limit}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()


class ClickHouseError(RuntimeError):
    pass


# ── the derived view + its checkpoint, exactly as the design commits them ──
# events: ReplacingMergeTree versioned by seq, ORDER BY event_id → re-inserting the same
#   event (a batch retried after a crash) collapses to ONE row at merge/FINAL — the
#   idempotency bar. Dual timestamps (wall_time = the log's clock, ingest_time = ours)
#   per pht.md commitment 3.
# materializer_checkpoint: one row per materializer name, versioned by cursor. The cursor
#   is monotonic, so max(cursor) is correct even before parts merge (no FINAL needed).
DDL = [
    "CREATE DATABASE IF NOT EXISTS hellgraph",
    """
    CREATE TABLE IF NOT EXISTS hellgraph.events (
      event_id    String,
      seq         UInt64,
      kind        LowCardinality(String),
      label       String,
      from_id     String,
      to_id       String,
      properties  String,
      wall_time   DateTime64(3, 'UTC'),
      ingest_time DateTime64(3, 'UTC') DEFAULT now64(3)
    ) ENGINE = ReplacingMergeTree(seq) ORDER BY event_id
    """,
    """
    CREATE TABLE IF NOT EXISTS hellgraph.materializer_checkpoint (
      materializer String,
      cursor       UInt64,
      updated_at   DateTime64(3, 'UTC') DEFAULT now64(3)
    ) ENGINE = ReplacingMergeTree(cursor) ORDER BY materializer
    """,
]

EVENT_COLUMNS = ("event_id", "seq", "kind", "label", "from_id", "to_id",
                 "properties", "wall_time")


class ClickHouseClient:
    """ClickHouse over its HTTP interface. Reads that must see deduped rows go through
    FINAL (SELECT ... FROM hellgraph.events FINAL) — ReplacingMergeTree dedups at merge
    time, so a plain SELECT may still see a retried batch twice; FINAL (or GROUP BY
    event_id + argMax) is the read-side half of the idempotency contract."""

    def __init__(self, url: str, user: str = "default", password: str = "") -> None:
        self.url = url.rstrip("/")
        self.user = user
        self.password = password

    def _headers(self) -> dict[str, str]:
        return {"X-ClickHouse-User": self.user, "X-ClickHouse-Key": self.password}

    def execute(self, sql: str, body: str | None = None) -> str:
        """Run one statement. When `body` is given, `sql` is passed as the query param and
        the body carries the data (the INSERT ... FORMAT JSONEachRow shape)."""
        if body is None:
            r = httpx.post(self.url, content=sql, headers=self._headers(), timeout=TIMEOUT)
        else:
            r = httpx.post(self.url, params={"query": sql}, content=body,
                           headers=self._headers(), timeout=TIMEOUT)
        if r.status_code != 200:
            raise ClickHouseError(f"clickhouse {r.status_code}: {r.text[:500]}")
        return r.text

    def ensure_schema(self) -> None:
        for stmt in DDL:
            self.execute(stmt.strip())

    def insert_events(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        cols = ", ".join(EVENT_COLUMNS)
        body = "\n".join(json.dumps({c: row[c] for c in EVENT_COLUMNS}, ensure_ascii=False)
                         for row in rows)
        self.execute(f"INSERT INTO hellgraph.events ({cols}) FORMAT JSONEachRow", body)

    def read_checkpoint(self, materializer: str) -> int:
        out = self.execute(
            "SELECT max(cursor) FROM hellgraph.materializer_checkpoint "
            f"WHERE materializer = '{materializer}'").strip()
        return int(out) if out else 0

    def write_checkpoint(self, materializer: str, cursor: int) -> None:
        body = json.dumps({"materializer": materializer, "cursor": cursor})
        self.execute(
            "INSERT INTO hellgraph.materializer_checkpoint (materializer, cursor) "
            "FORMAT JSONEachRow", body)


class GatewayError(RuntimeError):
    """Receipt minting failed — the batch MUST NOT be checkpointed (fail-closed)."""


class GatewayClient:
    """Seals one receipt per batch on the estate spine: POST /v1/compute with the
    `materialize` kind. The gateway hash-chains + Ed25519-attests it; the spec binds
    {from_cursor, to_cursor, row_count, batch_hash} into inputs_sha. Any failure —
    transport, auth, non-ok status — raises GatewayError so the caller cannot
    checkpoint an unattested batch."""

    def __init__(self, base_url: str, token: str, project: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project = project

    def mint(self, *, from_cursor: int, to_cursor: int, row_count: int,
             batch_hash: str, table: str = "hellgraph.events") -> dict[str, Any]:
        req = {
            "kind": "materialize",
            "project": self.project,
            "actor": "prophet-materializer-clickhouse",
            "spec": {
                "source": "hellgraph", "sink": "clickhouse", "table": table,
                "from_cursor": from_cursor, "to_cursor": to_cursor,
                "row_count": row_count, "batch_hash": batch_hash,
            },
        }
        try:
            r = httpx.post(f"{self.base_url}/v1/compute", json=req,
                           headers={"Authorization": f"Bearer {self.token}"}, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise GatewayError(f"compute-gateway unreachable: {e}") from e
        if r.status_code != 200:
            raise GatewayError(f"compute-gateway {r.status_code}: {r.text[:500]}")
        result = r.json()
        if result.get("status") != "ok" or not result.get("receipt"):
            raise GatewayError(f"materialize receipt refused: {json.dumps(result)[:500]}")
        return result["receipt"]
