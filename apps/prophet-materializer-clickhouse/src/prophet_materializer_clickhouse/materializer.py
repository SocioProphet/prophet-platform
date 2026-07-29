"""The materializer core — one governed batch per call, restart-safe by construction.

Order inside a logical batch (the WHOLE correctness argument):

    read checkpoint → poll log(since=checkpoint) → INSERT rows → mint receipt → INSERT checkpoint

- The checkpoint INSERT is the COMMIT POINT. Everything before it is idempotently
  repeatable: rows re-inserted after a crash collapse in ReplacingMergeTree (keyed by
  event_id, versioned by seq), and a re-minted identical batch memoizes to the SAME
  receipt on the gateway. Crash anywhere before the checkpoint ⇒ the next run replays
  the same cut and converges to the same state — zero duplicate rows at FINAL.
- The receipt comes BEFORE the checkpoint (fail-closed): if the estate spine cannot
  attest "materialized through cut X", the cut is not committed and the batch is
  retried. A view that cannot prove its currency does not advance.
- Empty poll ⇒ no receipt, no checkpoint — receipts attest work, not heartbeats.

Events arrive from hellgraph-service GET /api/graph/log (creation events, seq-ascending,
since-exclusive) and map 1:1 onto hellgraph.events rows:

    event_id   "node:<id>" | "edge:<link-handle>"   (the idempotency key)
    seq        the log's logical clock at creation   (the ReplacingMergeTree version)
    label      edge label, or the node's labels joined with ','
    properties the event's properties as canonical JSON (sorted keys)
    wall_time  the log's wall-clock timestamp; ingest_time is stamped by ClickHouse
               (dual timestamps — pht.md Design commitment 3)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .clients import GatewayError

MATERIALIZER_NAME = "clickhouse"


def to_row(event: dict[str, Any]) -> dict[str, Any]:
    kind = event["kind"]
    if kind == "node":
        label = ",".join(event.get("labels") or [])
        from_id, to_id = "", ""
    else:
        label = event.get("label") or ""
        from_id, to_id = event.get("from") or "", event.get("to") or ""
    return {
        "event_id": f"{kind}:{event['id']}",
        "seq": int(event["seq"]),
        "kind": kind,
        "label": label,
        "from_id": from_id,
        "to_id": to_id,
        "properties": json.dumps(event.get("properties") or {}, sort_keys=True,
                                 ensure_ascii=False, default=str),
        "wall_time": _clickhouse_ts(event.get("wallTime")),
    }


def _clickhouse_ts(iso: str | None) -> str:
    """ISO-8601 → 'YYYY-MM-DD HH:MM:SS.mmm' UTC — the one DateTime64 text form ClickHouse
    parses without best-effort settings. Unparseable/missing falls back to epoch zero
    (never dropped: the row's ordering truth is seq, not the wall clock)."""
    if iso:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
        except ValueError:
            pass
    return "1970-01-01 00:00:00.000"


def batch_hash(rows: list[dict[str, Any]]) -> str:
    """sha256 over the SORTED event_ids — order-independent, so the same cut always
    hashes the same and the gateway's memo can collapse a retried batch."""
    joined = "\n".join(sorted(r["event_id"] for r in rows))
    return "sha256:" + hashlib.sha256(joined.encode()).hexdigest()


@dataclass
class BatchResult:
    events: int = 0
    from_cursor: int = 0
    to_cursor: int = 0
    version: int = 0
    receipt_id: str | None = None
    batch_hash: str | None = None
    checkpointed: bool = False

    @property
    def lag(self) -> int:
        return max(0, self.version - self.to_cursor)


@dataclass
class Materializer:
    hellgraph: Any
    clickhouse: Any
    gateway: Any
    batch_limit: int = 500
    _schema_ready: bool = field(default=False, repr=False)

    def run_once(self) -> BatchResult:
        """One logical batch. Raises on ClickHouse/gateway failure — the caller's loop
        logs and retries; nothing is ever checkpointed past a failure (fail-closed)."""
        if not self._schema_ready:
            self.clickhouse.ensure_schema()
            self._schema_ready = True

        since = self.clickhouse.read_checkpoint(MATERIALIZER_NAME)
        page = self.hellgraph.poll(since=since, limit=self.batch_limit)
        events = page.get("events") or []
        version = int(page.get("version") or 0)
        if not events:
            # nothing to materialize — no receipt (attest work, not heartbeats), no checkpoint
            return BatchResult(events=0, from_cursor=since, to_cursor=since, version=version)

        rows = [to_row(e) for e in events]
        cut = int(page["cursor"])
        digest = batch_hash(rows)

        # 1) rows first — idempotent by construction (event_id key + seq version)
        self.clickhouse.insert_events(rows)
        # 2) receipt on the estate spine — a GatewayError aborts HERE, before the
        #    checkpoint, so the unattested cut is retried in full (fail-closed)
        receipt = self.gateway.mint(from_cursor=since, to_cursor=cut,
                                    row_count=len(rows), batch_hash=digest)
        # 3) the commit point
        self.clickhouse.write_checkpoint(MATERIALIZER_NAME, cut)

        return BatchResult(events=len(rows), from_cursor=since, to_cursor=cut,
                           version=version, receipt_id=receipt.get("id"),
                           batch_hash=digest, checkpointed=True)


__all__ = ["Materializer", "BatchResult", "GatewayError", "to_row", "batch_hash",
           "MATERIALIZER_NAME"]
