"""The emitter core — validate-then-write, one governed batch per call, restart-safe.

Write path (the whole point of W1.2 — events enter the platform log as graph writes):

    tick → build_event → VALIDATE (jsonschema, fail-closed) →
        POST /api/graph/node  {id: mde-<sym>-<seq>, labels: [MarketDataEvent, <symbol>],
                               properties: flattened event + full event JSON}
        POST /api/graph/edge  {label: aboutSymbol, from: <event node>, to: <symbol node>}

hellgraph-service appends both writes to its log; prophet-materializer-clickhouse (W1.1)
tails GET /api/graph/log and lands them in ClickHouse. This service never talks to
ClickHouse — the log is the only door (pht.md commitment 1).

Fail-closed rules, in order of severity:
- VALIDATION failure ⇒ the event is NOT emitted, counted, and logged loudly. The tick
  is dropped (a deterministically-invalid tick would wedge the stream forever); the
  count on /healthz is the alarm — its steady-state MUST be 0.
- HELLGRAPH failure ⇒ the batch stays PENDING and is retried next interval; no new
  ticks are generated while a batch is pending (bounded memory, gapless seq stream).
  Each pending item tracks node/edge completion separately: node re-POSTs are safe
  (upsert + ReplacingMergeTree dedup by event_id) but a re-added edge would mint a NEW
  log event and a duplicate ClickHouse row — so a half-emitted item never re-sends the
  half that landed.
- The loop never dies: any error is recorded in state and retried after the interval.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
import jsonschema

from .contract import build_event, flatten, local_id, startup_check, validate_event
from .generator import Tick, TickGenerator

log = logging.getLogger("market-replay")

TIMEOUT = 10.0
EVENT_LABEL = "MarketDataEvent"
SYMBOL_LABEL = "Symbol"
EDGE_LABEL = "aboutSymbol"


class EmitError(RuntimeError):
    """hellgraph-service unreachable or refused a write — retry, never crash-loop."""


class HellGraphWriter:
    """The one door out: POST /api/graph/node|edge on hellgraph-service. Injectable so
    unit tests prove batch semantics (shapes, retry, no duplicate edges) on a fake."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, payload: dict[str, Any]) -> None:
        try:
            r = httpx.post(f"{self.base_url}{path}", json=payload, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise EmitError(f"hellgraph unreachable: {e}") from e
        if r.status_code != 200:
            raise EmitError(f"hellgraph {r.status_code} on {path}: {r.text[:300]}")

    def post_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> None:
        self._post("/api/graph/node", {"id": node_id, "labels": labels, "properties": properties})

    def post_edge(self, label: str, from_id: str, to_id: str) -> None:
        self._post("/api/graph/edge", {"label": label, "from": from_id, "to": to_id})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class _Pending:
    """One validated event's remaining writes. node_done flips before the edge POST so
    a mid-item failure resumes exactly where it stopped."""
    event: dict[str, Any]
    node_id: str
    symbol: str
    seq: int
    node_done: bool = False


@dataclass
class BatchResult:
    generated: int = 0
    emitted: int = 0              # events whose node AND edge both landed this call
    validation_failures: int = 0
    pending: int = 0              # events still awaiting hellgraph after this call
    last_seq: int = 0
    hellgraph_ok: bool = True


@dataclass
class ReplayEmitter:
    generator: TickGenerator
    writer: Any                   # HellGraphWriter | test fake
    clock: Callable[[], str] = field(default=_utc_now_iso)
    _symbols_ensured: bool = field(default=False, repr=False)
    _pending: list[_Pending] = field(default_factory=list, repr=False)
    _last_seq: int = field(default=0, repr=False)

    def startup_check(self) -> None:
        """Boot gate: vendored-schema hash already asserted at import; here a probe
        event from a THROWAWAY generator (same seed) must validate. Raises on drift —
        the process must not come up able to emit non-conformant objects."""
        probe = TickGenerator(self.generator.symbols, self.generator.seed).next_tick(
            self.generator.symbols[0])
        startup_check(probe, self.clock())

    def ensure_symbols(self) -> None:
        """Upsert one Symbol node per configured symbol (id = the raw symbol string).
        Runs once per process; addNode is an upsert, so restarts are harmless."""
        for s in self.generator.symbols:
            self.writer.post_node(s, [SYMBOL_LABEL], {"symbol": s, "synthetic": True})
        self._symbols_ensured = True

    def run_once(self) -> BatchResult:
        """One interval: (re)try symbol nodes, drain any pending half-batch, and only
        when nothing is pending generate + validate + emit a fresh batch."""
        result = BatchResult(last_seq=self._last_seq)

        if not self._symbols_ensured:
            try:
                self.ensure_symbols()
            except EmitError as e:
                log.warning("symbol-node upsert failed, will retry: %s", e)
                result.hellgraph_ok = False
                result.pending = len(self._pending)
                return result

        if not self._pending:
            for tick in self.generator.next_batch():
                result.generated += 1
                event = build_event(tick, self.clock())
                try:
                    # THE fail-closed gate: nothing non-conformant may reach the log.
                    validate_event(event)
                except jsonschema.ValidationError as e:
                    result.validation_failures += 1
                    log.error("VALIDATION FAILURE — event NOT emitted (symbol=%s seq=%s): %s",
                              tick.symbol, tick.seq, e.message)
                    continue
                self._pending.append(_Pending(event=event, symbol=tick.symbol, seq=tick.seq,
                                              node_id=local_id(tick.symbol, tick.seq)))

        result.emitted, result.hellgraph_ok = self._drain()
        result.pending = len(self._pending)
        result.last_seq = self._last_seq
        return result

    def _drain(self) -> tuple[int, bool]:
        emitted = 0
        while self._pending:
            item = self._pending[0]
            try:
                if not item.node_done:
                    self.writer.post_node(
                        item.node_id, [EVENT_LABEL, item.symbol],
                        flatten(item.event, ingest_time=self.clock()))
                    item.node_done = True
                self.writer.post_edge(EDGE_LABEL, item.node_id, item.symbol)
            except EmitError as e:
                log.warning("hellgraph write failed at %s (seq=%s), batch stays pending: %s",
                            "edge" if item.node_done else "node", item.seq, e)
                return emitted, False
            self._pending.pop(0)
            emitted += 1
            self._last_seq = max(self._last_seq, item.seq)
        return emitted, True


__all__ = ["ReplayEmitter", "HellGraphWriter", "BatchResult", "EmitError",
           "EVENT_LABEL", "SYMBOL_LABEL", "EDGE_LABEL"]
