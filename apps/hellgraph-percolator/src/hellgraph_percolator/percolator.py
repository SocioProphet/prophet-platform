"""The percolator core — one governed batch per call, restart-safe by construction.

Order inside a batch (the whole correctness argument, mirroring prophet-materializer-clickhouse):

    read cursor → poll log(since=cursor) → percolate (re-materialise the affected closure) → mint receipt → advance cursor

- Percolation writes are UPSERTS (idempotent by node/edge id), so replaying a cut after a crash
  converges to the same graph — the checkpoint (cursor advance) is the commit point and everything
  before it is idempotently repeatable.
- The receipt comes BEFORE the checkpoint (fail-closed): if the spine cannot attest "percolated
  through cut X", the cut is not committed and the batch retries. A trigger that cannot prove its
  work does not advance.
- Empty poll ⇒ no receipt, no checkpoint — receipts attest work, not heartbeats.

Two triggers, one core: the LOG-TAIL path (`run_once`, cursor-ordered) and the ENVELOPE path
(`on_envelope`, an exchange-envelope.v0 delivered by webhook — not log-ordered, so it seals a
receipt but touches no cursor). Both rebuild the dependency catalog from LIVE graph state and land
the same scoped, isolation-carrying upserts through the shared library.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence

from tools.hellgraph_percolation.live import LivePercolator, changed_ids_from_log

from .clients import GatewayError  # noqa: F401 — re-exported for the loop's except clause


def batch_hash(ids: Sequence[str]) -> str:
    """sha256 over the SORTED ids — order-independent, so the same cut always hashes the same and the
    gateway's memo collapses a retried batch."""
    return "sha256:" + hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


@dataclass
class BatchResult:
    trigger: str = "log-tail"
    changed: int = 0          # seed ids the trigger announced (that exist in the catalog)
    materialized: int = 0     # objects in the re-materialised closure (what was written)
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
class Percolator:
    """Drives the live percolation loop. `graph` reads (log + subgraph), `writer` lands upserts, `gateway`
    seals receipts. The cursor is in-memory: on restart the loop re-scans from 0, which is safe because
    percolation upserts are idempotent (durable-cursor persistence is a tracked follow-on)."""

    graph: Any
    writer: Any
    gateway: Any
    batch_limit: int = 500
    cursor: int = 0

    def _live(self) -> LivePercolator:
        return LivePercolator(graph_reader=self.graph.read_subgraph, writer=self.writer)

    def run_once(self, *, now: str = "") -> BatchResult:
        """One log-tail batch. Raises (GatewayError / transport) on failure — the loop logs and retries;
        nothing is checkpointed past a failure (fail-closed)."""
        since = self.cursor
        page = self.graph.poll(since=since, limit=self.batch_limit)
        events = page.get("events") or []
        version = int(page.get("version") or 0)
        if not events:
            return BatchResult(from_cursor=since, to_cursor=since, version=version)

        cut = int(page["cursor"])
        changed = changed_ids_from_log(events)

        # 1) re-materialise the affected closure (idempotent upserts into the live graph)
        result = self._live().on_changed(changed, now=now)
        digest = batch_hash(result.order or changed)

        # 2) receipt on the spine — a GatewayError aborts HERE, before the cursor advances (fail-closed)
        receipt = self.gateway.mint(trigger="log-tail", from_cursor=since, to_cursor=cut,
                                    changed=len(changed), materialized=len(result.order),
                                    batch_hash=digest)
        # 3) the commit point
        self.cursor = cut

        return BatchResult(trigger="log-tail", changed=len(changed), materialized=len(result.order),
                           from_cursor=since, to_cursor=cut, version=version,
                           receipt_id=receipt.get("id"), batch_hash=digest, checkpointed=True)

    def on_envelope(self, envelope: Mapping, *, now: str = "") -> BatchResult:
        """The webhook path: percolate the change an exchange-envelope.v0 announces (tenant-scoped),
        then seal ONE receipt. Not log-ordered, so no cursor moves; the write is idempotent, so a
        receipt failure (which raises) is safely retryable by re-POSTing the envelope."""
        result = self._live().on_envelope(envelope, now=now)
        materialized: List[str] = list(result.order)
        digest = batch_hash(materialized)
        receipt = self.gateway.mint(trigger="exchange-envelope", from_cursor=self.cursor,
                                    to_cursor=self.cursor, changed=len(materialized),
                                    materialized=len(materialized), batch_hash=digest)
        return BatchResult(trigger="exchange-envelope", changed=len(materialized),
                           materialized=len(materialized), from_cursor=self.cursor,
                           to_cursor=self.cursor, version=0, receipt_id=receipt.get("id"),
                           batch_hash=digest, checkpointed=True)


__all__ = ["Percolator", "BatchResult", "GatewayError", "batch_hash"]
