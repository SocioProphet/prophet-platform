#!/usr/bin/env python3
"""OTel / OpenInference observability scaffold (Workspace Control Plane, Phase 9).

Scaffold-first: OpenTelemetry trace semantics — span tree, attributes, events,
status, and exporters — implemented in-process with **no opentelemetry-sdk
dependency**. When the real OTel SDK is added, swap the provider/exporter
behind the same ``Tracer`` / ``SpanExporter`` interfaces; the semantic
conventions and span contract do not change.

Semantic conventions implemented here follow:
  - OpenTelemetry Trace API (span ID, trace ID, parent, status)
  - OpenInference v0.0.8 (span.kind, input.value, output.value,
    retrieval.documents, embedding.*)
  - Prophet Platform extensions (workflow.*, claim.*, approval.*)

Design decisions:
  D14 — Every state transition in TemporalOutbox emits a span.  Approvals
         carry approver + decision as typed attributes, not free-form strings.
  D15 — Every MemoryStore ingest/recall emits a span tagged with the tier,
         subject, and result count; recall_similar spans include the query.
"""
from __future__ import annotations

import contextlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Semantic attribute keys ───────────────────────────────────────────────────

# Prophet Platform — workflow
WORKFLOW_RUN_ID        = "workflow.run_id"
WORKFLOW_STATUS_BEFORE = "workflow.status.before"
WORKFLOW_STATUS_AFTER  = "workflow.status.after"
WORKFLOW_OUTBOX_STATE  = "workflow.outbox_state"

# Prophet Platform — approval
APPROVAL_APPROVER  = "approval.approver"
APPROVAL_DECISION  = "approval.decision"
APPROVAL_AUTHORIZED = "approval.authorized"

# Prophet Platform — claim
CLAIM_ID                 = "claim.claim_id"
CLAIM_SUBJECT            = "claim.subject"
CLAIM_EPISTEMIC_LEVEL    = "claim.epistemic_level"
CLAIM_CONFIDENCE         = "claim.confidence"
CLAIM_METHOD             = "claim.method"
CLAIM_CONTRADICTION_STATUS = "claim.contradiction_status"

# Prophet Platform — memory
MEMORY_TIER          = "memory.tier"
MEMORY_RESULT_COUNT  = "memory.result_count"
MEMORY_QUERY         = "memory.query"
MEMORY_SUBJECT       = "memory.subject"
MEMORY_TERM          = "memory.term"

# OpenInference
OPENINFERENCE_SPAN_KIND       = "openinference.span.kind"
OPENINFERENCE_INPUT_VALUE     = "input.value"
OPENINFERENCE_OUTPUT_VALUE    = "output.value"
OPENINFERENCE_RETRIEVAL_DOCS  = "retrieval.documents"

# OpenInference span kinds
SPAN_KIND_CHAIN    = "CHAIN"
SPAN_KIND_RETRIEVER = "RETRIEVER"
SPAN_KIND_TOOL     = "TOOL"
SPAN_KIND_GUARDRAIL = "GUARDRAIL"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds")


def _span_id() -> str:
    return uuid.uuid4().hex[:16]


def _trace_id() -> str:
    return uuid.uuid4().hex


# ── Core data structures ──────────────────────────────────────────────────────

@dataclass
class SpanEvent:
    name: str
    timestamp: str = field(default_factory=_now_iso)
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "timestamp": self.timestamp,
                "attributes": dict(self.attributes)}


@dataclass
class Span:
    """A single unit of work within a trace.

    Immutable after ``finish()`` — raises ``RuntimeError`` if mutated post-close.
    """
    name: str
    span_id: str = field(default_factory=_span_id)
    trace_id: str = field(default_factory=_trace_id)
    parent_span_id: Optional[str] = None
    start_time: str = field(default_factory=_now_iso)
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str = "unset"           # ok | error | unset
    error_message: Optional[str] = None
    attributes: dict = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    _finished: bool = field(default=False, init=False, repr=False)
    _start_mono: float = field(default_factory=time.monotonic, init=False, repr=False)
    _exporter: Optional["SpanExporter"] = field(default=None, init=False, repr=False)

    def _guard(self) -> None:
        if self._finished:
            raise RuntimeError(f"span '{self.name}' ({self.span_id}) is already finished")

    def set_attribute(self, key: str, value: object) -> "Span":
        self._guard()
        self.attributes[key] = value
        return self

    def add_event(self, name: str, attributes: Optional[dict] = None) -> "Span":
        self._guard()
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))
        return self

    def finish(self, status: str = "ok", error: Optional[str] = None) -> "Span":
        self._guard()
        self.end_time = _now_iso()
        self.duration_ms = round((time.monotonic() - self._start_mono) * 1000, 3)
        self.status = status
        self.error_message = error
        self._finished = True
        if self._exporter is not None:
            self._exporter.export(self)
        return self

    @property
    def finished(self) -> bool:
        return self._finished

    def to_dict(self) -> dict:
        return {
            "span_id":        self.span_id,
            "trace_id":       self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name":           self.name,
            "start_time":     self.start_time,
            "end_time":       self.end_time,
            "duration_ms":    self.duration_ms,
            "status":         self.status,
            "error_message":  self.error_message,
            "attributes":     dict(self.attributes),
            "events":         [e.to_dict() for e in self.events],
        }


# ── Exporter protocol ─────────────────────────────────────────────────────────

class SpanExporter:
    """Base exporter interface — override ``export()``."""

    def export(self, span: Span) -> None:  # noqa: B027  (intentional no-op)
        pass

    def shutdown(self) -> None:
        pass


class InMemoryExporter(SpanExporter):
    """Collects finished spans in memory (thread-safe). Use in tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spans: list[dict] = []

    def export(self, span: Span) -> None:
        with self._lock:
            self._spans.append(span.to_dict())

    @property
    def spans(self) -> list[dict]:
        with self._lock:
            return list(self._spans)

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()


class JSONLinesExporter(SpanExporter):
    """Appends one JSON line per finished span to a file."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

    def export(self, span: Span) -> None:
        line = json.dumps(span.to_dict(), separators=(",", ":"))
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")


# ── Tracer ────────────────────────────────────────────────────────────────────

class Tracer:
    """Create and manage spans.

    All spans created by this tracer share the same exporter.
    Pass ``parent_span`` to create a child span that inherits the parent's
    trace_id and records its span_id as parent_span_id.
    """

    def __init__(self, exporter: Optional[SpanExporter] = None) -> None:
        self._exporter = exporter or SpanExporter()

    def start_span(
        self,
        name: str,
        *,
        parent_span: Optional[Span] = None,
        attributes: Optional[dict] = None,
    ) -> Span:
        span = Span(name=name)
        if parent_span is not None:
            span.trace_id = parent_span.trace_id
            span.parent_span_id = parent_span.span_id
        if attributes:
            span.attributes.update(attributes)
        span._exporter = self._exporter
        return span

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        *,
        parent_span: Optional[Span] = None,
        attributes: Optional[dict] = None,
    ):
        """Context manager: starts a span, finishes it on exit (status=error on exc)."""
        s = self.start_span(name, parent_span=parent_span, attributes=attributes)
        try:
            yield s
            if not s.finished:
                s.finish(status="ok")
        except Exception as exc:
            if not s.finished:
                s.finish(status="error", error=str(exc))
            raise


# ── Instrumentation helpers ───────────────────────────────────────────────────

def instrument_outbox(outbox, tracer: Tracer) -> None:
    """Wrap TemporalOutbox to emit spans on every state transition.

    This is a non-invasive patch applied at runtime; the outbox internals
    are unchanged. Spans carry workflow.* and approval.* attributes.
    """
    original_create  = outbox.create
    original_start   = outbox.start
    original_complete = outbox.complete
    original_fail    = outbox.fail
    original_approve = outbox.approve

    def _create(case_id, activity, actor, object_refs, *, inputs=None, run_id=None):
        with tracer.span("workflow.create", attributes={
            WORKFLOW_STATUS_BEFORE:  "none",
            WORKFLOW_STATUS_AFTER:   "pending",
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_CHAIN,
        }) as sp:
            result = original_create(case_id, activity, actor, object_refs,
                                     inputs=inputs, run_id=run_id)
            sp.set_attribute(WORKFLOW_RUN_ID, result.run_id)
            sp.add_event("run.created")
            return result

    def _start(run_id: str):
        run = outbox._runs.get(run_id)
        before = run.status if run else "unknown"
        with tracer.span("workflow.start", attributes={
            WORKFLOW_RUN_ID:        run_id,
            WORKFLOW_STATUS_BEFORE:  before,
            WORKFLOW_STATUS_AFTER:   "running",
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_CHAIN,
        }) as sp:
            sp.add_event("run.started")
            return original_start(run_id)

    def _complete(run_id: str, *, outputs=None, state_delta=None):
        run = outbox._runs.get(run_id)
        before = run.status if run else "unknown"
        with tracer.span("workflow.complete", attributes={
            WORKFLOW_RUN_ID:        run_id,
            WORKFLOW_STATUS_BEFORE:  before,
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_CHAIN,
        }) as sp:
            result = original_complete(run_id, outputs=outputs, state_delta=state_delta)
            after = outbox._runs[run_id].status if run_id in outbox._runs else "succeeded"
            sp.set_attribute(WORKFLOW_STATUS_AFTER, after)
            return result

    def _fail(run_id: str, *, reason: str = ""):
        run = outbox._runs.get(run_id)
        before = run.status if run else "unknown"
        with tracer.span("workflow.fail", attributes={
            WORKFLOW_RUN_ID:        run_id,
            WORKFLOW_STATUS_BEFORE:  before,
            WORKFLOW_STATUS_AFTER:   "failed",
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_CHAIN,
        }) as sp:
            sp.add_event("run.failed", {"reason": reason})
            return original_fail(run_id, reason=reason)

    def _approve(run_id: str, *, approver: str, decision: str,
                 authorized_approvers: list):
        authorized = approver in authorized_approvers
        attrs = {
            WORKFLOW_RUN_ID:         run_id,
            APPROVAL_APPROVER:       approver,
            APPROVAL_DECISION:       decision,
            APPROVAL_AUTHORIZED:     authorized,
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_GUARDRAIL,
        }
        with tracer.span("workflow.approve", attributes=attrs) as sp:
            if not authorized:
                sp.add_event("approval.denied", {"approver": approver})
            result = original_approve(
                run_id, approver=approver, decision=decision,
                authorized_approvers=authorized_approvers,
            )
            sp.add_event("approval.recorded", {"decision": decision})
            return result

    outbox.create  = _create
    outbox.start   = _start
    outbox.complete = _complete
    outbox.fail    = _fail
    outbox.approve = _approve


def instrument_memory(store, tracer: Tracer) -> None:
    """Wrap MemoryStore to emit spans on ingest and recall operations.

    Spans carry claim.* and memory.* attributes per OpenInference conventions.
    """
    original_ingest        = store.ingest
    original_recall_recent = store.recall_recent
    original_by_subject    = store.recall_by_subject
    original_similar       = store.recall_similar
    original_by_term       = store.recall_by_term

    def _ingest(claim: dict):
        attrs = {
            CLAIM_ID:                  claim.get("claim_id", ""),
            CLAIM_SUBJECT:             claim.get("subject", ""),
            CLAIM_EPISTEMIC_LEVEL:     claim.get("epistemic_level", ""),
            CLAIM_CONFIDENCE:          claim.get("confidence", 0.0),
            CLAIM_METHOD:              (claim.get("provenance") or {}).get("method", ""),
            CLAIM_CONTRADICTION_STATUS: claim.get("contradiction_status", ""),
            MEMORY_TIER:               "ingest",
            OPENINFERENCE_SPAN_KIND:   SPAN_KIND_TOOL,
        }
        with tracer.span("memory.ingest", attributes=attrs):
            return original_ingest(claim)

    def _recall_recent(n: int = 10):
        with tracer.span("memory.recall_recent", attributes={
            MEMORY_TIER: "T1",
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_RETRIEVER,
            OPENINFERENCE_INPUT_VALUE: str(n),
        }) as sp:
            result = original_recall_recent(n)
            sp.set_attribute(MEMORY_RESULT_COUNT, len(result))
            return result

    def _recall_by_subject(subject: str):
        with tracer.span("memory.recall_by_subject", attributes={
            MEMORY_TIER:    "T2",
            MEMORY_SUBJECT: subject,
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_RETRIEVER,
        }) as sp:
            result = original_by_subject(subject)
            sp.set_attribute(MEMORY_RESULT_COUNT, len(result))
            return result

    def _recall_similar(statement: str, *, top_k: int = 5):
        with tracer.span("memory.recall_similar", attributes={
            MEMORY_TIER:  "T3",
            MEMORY_QUERY: statement[:200],
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_RETRIEVER,
            OPENINFERENCE_INPUT_VALUE: statement[:200],
        }) as sp:
            result = original_similar(statement, top_k=top_k)
            sp.set_attribute(MEMORY_RESULT_COUNT, len(result))
            if result:
                sp.set_attribute(OPENINFERENCE_OUTPUT_VALUE,
                                 json.dumps([r.get("claim_id") for r in result]))
            return result

    def _recall_by_term(term: str):
        with tracer.span("memory.recall_by_term", attributes={
            MEMORY_TIER: "T4",
            MEMORY_TERM: term,
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_RETRIEVER,
        }) as sp:
            result = original_by_term(term)
            sp.set_attribute(MEMORY_RESULT_COUNT, len(result))
            return result

    store.ingest            = _ingest
    store.recall_recent     = _recall_recent
    store.recall_by_subject = _recall_by_subject
    store.recall_similar    = _recall_similar
    store.recall_by_term    = _recall_by_term
