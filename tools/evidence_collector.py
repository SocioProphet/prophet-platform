#!/usr/bin/env python3
"""Evidence ingestion pipeline (Workspace Control Plane, Phase 11 / D18, D19).

Closes the loop: raw event sources (git log, CI events, audit trail, plain text)
→ ``ClaimExtractor`` → ``MemoryStore`` → ``PolicyGate`` evaluations → typed
``PolicyDecision`` records, all wired through the OTel span tree.

Scaffold-first: sources are pluggable ``EventSource`` objects; swap real adapters
(GitHub Events API, Buildkite webhooks, SIEM audit logs) behind the same interface.
The scheduler runs in-process with ``threading.Timer``; swap for APScheduler or
Temporal when the infra is ready.

Design decisions:
  D18 — The collector is stateless between runs: each tick reads all events from
         the source since ``last_collected_at``, extracts claims, ingests into
         the store, and returns a ``CollectionReport``. No persistent state is
         required in the scaffold; add a ``StateStore`` adapter later.
  D19 — Policies are evaluated immediately after each collection tick, so the
         governance verdict is always fresh: new evidence can clear a previous
         ``blocked`` or introduce a new one. The report carries both the ingested
         claim count and the policy decision for full auditability.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from memory_tier import ClaimExtractor, MemoryStore  # type: ignore
from otel_tracer import (  # type: ignore
    Tracer,
    OPENINFERENCE_SPAN_KIND,
    SPAN_KIND_CHAIN,
    SPAN_KIND_TOOL,
    MEMORY_TIER,
)
from policy_gate import Policy, PolicyGate  # type: ignore


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


# ── Event / EventSource ───────────────────────────────────────────────────────

@dataclass
class Event:
    """A single raw event from a source.

    Args:
        source_id: identifier of the originating system (e.g. ``git:repo/sha``)
        text: free-text payload to extract claims from
        event_type: categorical tag (``git_commit``, ``ci_run``, ``audit_record``, …)
        timestamp: ISO-8601 when the event was produced (defaults to now)
    """
    source_id: str
    text: str
    event_type: str = "generic"
    timestamp: str = field(default_factory=_now)


class EventSource:
    """Base class — override ``fetch()`` to adapt a real source."""

    def fetch(self, since: Optional[str] = None) -> list[Event]:
        return []


class InMemoryEventSource(EventSource):
    """Accepts events pushed via ``push()``; useful in tests and integration."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._consumed: int = 0

    def push(self, *events: Event) -> None:
        self._events.extend(events)

    def fetch(self, since: Optional[str] = None) -> list[Event]:
        batch = list(self._events[self._consumed:])
        self._consumed += len(batch)
        return batch


class StaticTextSource(EventSource):
    """Yield a fixed list of (source_id, text) pairs once then stop."""

    def __init__(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)
        self._done = False

    def fetch(self, since: Optional[str] = None) -> list[Event]:
        if self._done:
            return []
        self._done = True
        return [Event(source_id=sid, text=txt) for sid, txt in self._items]


# ── CollectionReport ──────────────────────────────────────────────────────────

@dataclass
class CollectionReport:
    """Result of one collection tick."""
    report_id: str = field(default_factory=lambda: f"cr-{uuid.uuid4().hex[:10]}")
    collected_at: str = field(default_factory=_now)
    events_fetched: int = 0
    claims_extracted: int = 0
    claims_ingested: int = 0
    ingest_errors: int = 0
    policy_decisions: list[dict] = field(default_factory=list)
    span_trace_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "report_id":        self.report_id,
            "collected_at":     self.collected_at,
            "events_fetched":   self.events_fetched,
            "claims_extracted": self.claims_extracted,
            "claims_ingested":  self.claims_ingested,
            "ingest_errors":    self.ingest_errors,
            "policy_decisions": list(self.policy_decisions),
            "span_trace_id":    self.span_trace_id,
            "error":            self.error,
        }


# ── EvidenceCollector ─────────────────────────────────────────────────────────

class EvidenceCollector:
    """Fetch → extract → ingest → evaluate pipeline.

    Each ``collect()`` call is a single tick. The optional ``schedule()`` /
    ``cancel()`` pair runs ticks on a recurring ``threading.Timer`` (scaffold).

    Args:
        source: the ``EventSource`` to poll
        extractor: ``ClaimExtractor`` instance
        store: ``MemoryStore`` to ingest claims into
        policies: list of ``Policy`` objects evaluated after each tick
        tracer: ``Tracer`` for OTel spans (CHAIN root wraps all sub-spans)
        min_text_length: events shorter than this are skipped (noise gate)
    """

    def __init__(
        self,
        source: EventSource,
        extractor: ClaimExtractor,
        store: MemoryStore,
        *,
        policies: Optional[list[Policy]] = None,
        tracer: Optional[Tracer] = None,
        min_text_length: int = 20,
    ) -> None:
        self._source = source
        self._extractor = extractor
        self._store = store
        self._policies = list(policies or [])
        self._tracer = tracer or Tracer()
        self._min_text_length = min_text_length
        self._last_collected_at: Optional[str] = None
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def add_policy(self, policy: Policy) -> None:
        self._policies.append(policy)

    def collect(self) -> CollectionReport:
        """Run one fetch → extract → ingest → evaluate tick.

        Returns a ``CollectionReport`` — always, even on error (fail-soft so the
        scheduler does not crash).
        """
        report = CollectionReport()
        root_attrs = {
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_CHAIN,
            "collector.source":      type(self._source).__name__,
            "collector.policy_count": len(self._policies),
        }
        with self._tracer.span("evidence.collect", attributes=root_attrs) as root:
            report.span_trace_id = root.trace_id
            try:
                self._tick(report, root)
            except Exception as exc:
                report.error = str(exc)
                root.add_event("collect.error", {"error": str(exc)})
        return report

    def _tick(self, report: CollectionReport, root_span) -> None:
        # ── fetch ────────────────────────────────────────────────────────────
        with self._tracer.span("evidence.fetch", parent_span=root_span,
                               attributes={OPENINFERENCE_SPAN_KIND: SPAN_KIND_TOOL}) as fs:
            events = self._source.fetch(since=self._last_collected_at)
            report.events_fetched = len(events)
            fs.set_attribute("collector.events_fetched", len(events))
            self._last_collected_at = _now()

        # ── extract + ingest ─────────────────────────────────────────────────
        for evt in events:
            if len(evt.text) < self._min_text_length:
                continue
            with self._tracer.span(
                "evidence.extract",
                parent_span=root_span,
                attributes={
                    OPENINFERENCE_SPAN_KIND: SPAN_KIND_TOOL,
                    "event.source_id": evt.source_id,
                    "event.event_type": evt.event_type,
                    MEMORY_TIER: "ingest",
                },
            ) as es:
                claims = self._extractor.extract(
                    evt.source_id, evt.text, method=f"rule_based_v0:{evt.event_type}"
                )
                report.claims_extracted += len(claims)
                es.set_attribute("extract.claim_count", len(claims))
                for claim in claims:
                    try:
                        self._store.ingest(claim)
                        report.claims_ingested += 1
                    except ValueError:
                        report.ingest_errors += 1

        # ── evaluate policies ────────────────────────────────────────────────
        gate = PolicyGate(self._store, self._tracer)
        for policy in self._policies:
            with self._tracer.span(
                f"evidence.evaluate.{policy.policy_id}",
                parent_span=root_span,
                attributes={
                    OPENINFERENCE_SPAN_KIND: SPAN_KIND_CHAIN,
                    "policy.policy_id": policy.policy_id,
                },
            ):
                decision = gate.evaluate(policy)
                report.policy_decisions.append(decision)

        root_span.set_attribute("collector.claims_ingested", report.claims_ingested)
        root_span.set_attribute("collector.decisions", len(report.policy_decisions))

    # ── Scheduler (scaffold) ──────────────────────────────────────────────────

    def schedule(self, interval_s: float) -> None:
        """Start recurring ticks every ``interval_s`` seconds (scaffold)."""
        self.cancel()
        self._schedule_next(interval_s)

    def _schedule_next(self, interval_s: float) -> None:
        def _tick_and_reschedule():
            self.collect()
            with self._lock:
                if self._timer is not None:
                    self._schedule_next(interval_s)
        with self._lock:
            self._timer = threading.Timer(interval_s, _tick_and_reschedule)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        """Stop the scheduler if running."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
