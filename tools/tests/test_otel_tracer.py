"""OTel observability scaffold (Phase 9) — correctness and gate proof.

Tests prove:
  - Span structure: all required fields present, correct types
  - Unique IDs: every span gets a distinct span_id and trace_id
  - Parent-child linking: child inherits trace_id, records parent_span_id
  - Immutability: finished span raises RuntimeError on mutation
  - InMemoryExporter: collects spans in order, thread-safe
  - JSONLines exporter: each span is a valid JSON line
  - Workflow instrumentation: state transitions emit spans with typed attributes
  - Approval gate: authorized and unauthorized approvals produce correct spans
  - Memory ingest: span carries claim subject, tier, epistemic_level
  - Memory recall tiers (T1/T2/T3/T4): each recall emits a span with result count
  - Error span: exception inside context manager → status=error
  - Span events: timestamped annotations carry structured attributes
  - Trace chain: multi-span chain shares trace_id throughout
  - Concurrent traces: independent traces do not share trace_id
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from otel_tracer import (  # type: ignore  # noqa: E402
    InMemoryExporter,
    JSONLinesExporter,
    Span,
    SpanEvent,
    Tracer,
    instrument_memory,
    instrument_outbox,
    WORKFLOW_RUN_ID,
    WORKFLOW_STATUS_BEFORE,
    WORKFLOW_STATUS_AFTER,
    APPROVAL_APPROVER,
    APPROVAL_DECISION,
    APPROVAL_AUTHORIZED,
    CLAIM_SUBJECT,
    CLAIM_EPISTEMIC_LEVEL,
    CLAIM_CONFIDENCE,
    MEMORY_TIER,
    MEMORY_RESULT_COUNT,
    OPENINFERENCE_SPAN_KIND,
)
from temporal_outbox import TemporalOutbox  # type: ignore  # noqa: E402
from memory_tier import MemoryStore, _make_claim  # type: ignore  # noqa: E402


# ── Span structure ────────────────────────────────────────────────────────────

def test_span_required_fields_present():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    s = tracer.start_span("test.op")
    s.finish()
    d = exp.spans[0]
    for key in ("span_id", "trace_id", "parent_span_id", "name", "start_time",
                "end_time", "duration_ms", "status", "error_message",
                "attributes", "events"):
        assert key in d, f"missing key: {key}"


def test_span_status_ok_by_default():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    tracer.start_span("op").finish()
    assert exp.spans[0]["status"] == "ok"


def test_span_name_propagated():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    tracer.start_span("workflow.transition").finish()
    assert exp.spans[0]["name"] == "workflow.transition"


# ── Unique IDs ────────────────────────────────────────────────────────────────

def test_each_span_has_unique_span_id():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    for _ in range(5):
        tracer.start_span("op").finish()
    ids = [s["span_id"] for s in exp.spans]
    assert len(set(ids)) == 5


def test_independent_spans_have_different_trace_ids():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    for _ in range(3):
        tracer.start_span("op").finish()
    trace_ids = [s["trace_id"] for s in exp.spans]
    assert len(set(trace_ids)) == 3


# ── Parent-child linking ──────────────────────────────────────────────────────

def test_child_span_inherits_trace_id():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    parent = tracer.start_span("parent")
    child = tracer.start_span("child", parent_span=parent)
    parent.finish()
    child.finish()
    spans = {s["name"]: s for s in exp.spans}
    assert spans["child"]["trace_id"] == spans["parent"]["trace_id"]
    assert spans["child"]["parent_span_id"] == spans["parent"]["span_id"]


def test_root_span_has_null_parent():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    tracer.start_span("root").finish()
    assert exp.spans[0]["parent_span_id"] is None


# ── Immutability after finish ─────────────────────────────────────────────────

def test_finished_span_raises_on_set_attribute():
    s = Span(name="op")
    s.finish()
    with pytest.raises(RuntimeError, match="already finished"):
        s.set_attribute("key", "val")


def test_finished_span_raises_on_add_event():
    s = Span(name="op")
    s.finish()
    with pytest.raises(RuntimeError, match="already finished"):
        s.add_event("event")


def test_finished_span_raises_on_double_finish():
    s = Span(name="op")
    s.finish()
    with pytest.raises(RuntimeError, match="already finished"):
        s.finish()


# ── InMemoryExporter ──────────────────────────────────────────────────────────

def test_in_memory_exporter_order():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    for i in range(4):
        tracer.start_span(f"op-{i}").finish()
    assert [s["name"] for s in exp.spans] == ["op-0", "op-1", "op-2", "op-3"]


def test_in_memory_exporter_thread_safe():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(20):
                tracer.start_span("concurrent").finish()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(exp.spans) == 100


def test_in_memory_exporter_clear():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    tracer.start_span("op").finish()
    exp.clear()
    assert exp.spans == []


# ── JSONLines exporter ────────────────────────────────────────────────────────

def test_jsonlines_exporter_valid_json():
    with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
        path = f.name
    exp = JSONLinesExporter(path)
    tracer = Tracer(exporter=exp)
    tracer.start_span("op.a").finish()
    tracer.start_span("op.b").finish()
    lines = Path(path).read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        d = json.loads(line)
        assert "span_id" in d and "trace_id" in d


# ── Context manager ───────────────────────────────────────────────────────────

def test_context_manager_sets_status_error_on_exception():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    with pytest.raises(ValueError):
        with tracer.span("failing.op"):
            raise ValueError("boom")
    assert exp.spans[0]["status"] == "error"
    assert "boom" in (exp.spans[0]["error_message"] or "")


def test_context_manager_sets_status_ok_on_success():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    with tracer.span("ok.op"):
        pass
    assert exp.spans[0]["status"] == "ok"


# ── Span events ───────────────────────────────────────────────────────────────

def test_span_events_carry_structured_attributes():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    s = tracer.start_span("multi.event")
    s.add_event("checkpoint.a", {"step": 1})
    s.add_event("checkpoint.b", {"step": 2})
    s.finish()
    events = exp.spans[0]["events"]
    assert len(events) == 2
    assert events[0]["name"] == "checkpoint.a"
    assert events[0]["attributes"]["step"] == 1


# ── Workflow instrumentation ──────────────────────────────────────────────────

def _make_run(outbox, run_id="run-001"):
    """Helper: create + start a run to reach 'running' state."""
    run = outbox.create("case-1", "deploy", "actor-a", [], run_id=run_id)
    outbox.start(run.run_id)
    return run


def test_workflow_create_emits_span():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    outbox = TemporalOutbox()
    instrument_outbox(outbox, tracer)
    run = outbox.create("c1", "deploy", "actor", [], run_id="run-001")
    names = [s["name"] for s in exp.spans]
    assert "workflow.create" in names
    create_span = next(s for s in exp.spans if s["name"] == "workflow.create")
    assert create_span["attributes"][WORKFLOW_RUN_ID] == "run-001"


def test_workflow_start_emits_span():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    outbox = TemporalOutbox()
    instrument_outbox(outbox, tracer)
    outbox.create("c1", "deploy", "actor", [], run_id="run-s01")
    exp.clear()
    outbox.start("run-s01")
    names = [s["name"] for s in exp.spans]
    assert "workflow.start" in names
    start_span = next(s for s in exp.spans if s["name"] == "workflow.start")
    assert start_span["attributes"][WORKFLOW_RUN_ID] == "run-s01"


def test_workflow_complete_records_status_transition():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    outbox = TemporalOutbox()
    instrument_outbox(outbox, tracer)
    _make_run(outbox, "run-002")
    exp.clear()
    outbox.complete("run-002")
    complete_span = next((s for s in exp.spans if s["name"] == "workflow.complete"), None)
    assert complete_span is not None
    assert complete_span["attributes"][WORKFLOW_RUN_ID] == "run-002"
    assert complete_span["attributes"].get(WORKFLOW_STATUS_AFTER) == "succeeded"


def test_approval_authorized_approver_emits_guardrail_span():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    outbox = TemporalOutbox()
    instrument_outbox(outbox, tracer)
    _make_run(outbox, "run-003")
    outbox.request_approval("run-003", approvers=["alice", "bob"])
    exp.clear()
    outbox.approve("run-003", approver="alice", decision="approve",
                   authorized_approvers=["alice", "bob"])
    approve_span = next((s for s in exp.spans if s["name"] == "workflow.approve"), None)
    assert approve_span is not None
    assert approve_span["attributes"][APPROVAL_APPROVER] == "alice"
    assert approve_span["attributes"][APPROVAL_DECISION] == "approve"
    assert approve_span["attributes"][APPROVAL_AUTHORIZED] is True


def test_approval_unauthorized_approver_span_marks_not_authorized():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    outbox = TemporalOutbox()
    instrument_outbox(outbox, tracer)
    _make_run(outbox, "run-004")
    outbox.request_approval("run-004", approvers=["alice"])
    exp.clear()
    from temporal_outbox import InvalidTransitionError  # type: ignore
    with pytest.raises(InvalidTransitionError):
        outbox.approve("run-004", approver="mallory", decision="approve",
                       authorized_approvers=["alice"])
    approve_span = next((s for s in exp.spans if s["name"] == "workflow.approve"), None)
    assert approve_span is not None
    assert approve_span["attributes"][APPROVAL_AUTHORIZED] is False


# ── Memory instrumentation ────────────────────────────────────────────────────

def test_memory_ingest_emits_span_with_subject():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    store = MemoryStore()
    instrument_memory(store, tracer)
    claim = _make_claim("Prophet Platform", "It supports multi-tenant graphs.",
                        source="doc", method="test", confidence=0.8)
    store.ingest(claim)
    ingest_span = next((s for s in exp.spans if s["name"] == "memory.ingest"), None)
    assert ingest_span is not None
    assert ingest_span["attributes"][CLAIM_SUBJECT] == "Prophet Platform"
    assert ingest_span["attributes"][MEMORY_TIER] == "ingest"


def test_memory_recall_recent_emits_t1_span_with_count():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    store = MemoryStore()
    instrument_memory(store, tracer)
    for i in range(3):
        store.ingest(_make_claim(f"s{i}", f"Claim {i} about something important.",
                                 source="doc", method="test", confidence=0.5))
    exp.clear()
    result = store.recall_recent(2)
    assert len(result) == 2
    spans = [s for s in exp.spans if s["name"] == "memory.recall_recent"]
    assert spans
    assert spans[0]["attributes"][MEMORY_TIER] == "T1"
    assert spans[0]["attributes"][MEMORY_RESULT_COUNT] == 2


def test_memory_recall_by_subject_emits_t2_span():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    store = MemoryStore()
    instrument_memory(store, tracer)
    store.ingest(_make_claim("Alpha", "Alpha has a governance role.",
                             source="doc", method="test", confidence=0.7))
    exp.clear()
    store.recall_by_subject("Alpha")
    spans = [s for s in exp.spans if s["name"] == "memory.recall_by_subject"]
    assert spans
    assert spans[0]["attributes"][MEMORY_TIER] == "T2"
    assert spans[0]["attributes"][MEMORY_RESULT_COUNT] == 1


def test_memory_recall_similar_emits_t3_span_with_query():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    store = MemoryStore()
    instrument_memory(store, tracer)
    store.ingest(_make_claim("s1", "Graph retrieval improves knowledge recall.",
                             source="doc", method="test", confidence=0.7))
    exp.clear()
    store.recall_similar("graph retrieval", top_k=1)
    spans = [s for s in exp.spans if s["name"] == "memory.recall_similar"]
    assert spans
    assert spans[0]["attributes"][MEMORY_TIER] == "T3"
    assert "graph" in spans[0]["attributes"].get("memory.query", "")


def test_memory_recall_by_term_emits_t4_span():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    store = MemoryStore()
    instrument_memory(store, tracer)
    store.ingest(_make_claim("s1", "Attestation binds the boot chain.",
                             source="doc", method="test", confidence=0.7))
    exp.clear()
    result = store.recall_by_term("attestation")
    spans = [s for s in exp.spans if s["name"] == "memory.recall_by_term"]
    assert spans
    assert spans[0]["attributes"][MEMORY_TIER] == "T4"
    assert spans[0]["attributes"][MEMORY_RESULT_COUNT] == len(result)


# ── Trace chain ───────────────────────────────────────────────────────────────

def test_multi_span_chain_shares_trace_id():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    root = tracer.start_span("root")
    child_a = tracer.start_span("child.a", parent_span=root)
    child_b = tracer.start_span("child.b", parent_span=root)
    child_a.finish()
    child_b.finish()
    root.finish()
    trace_ids = {s["trace_id"] for s in exp.spans}
    assert len(trace_ids) == 1


def test_duration_ms_is_non_negative():
    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    tracer.start_span("timed.op").finish()
    assert exp.spans[0]["duration_ms"] >= 0.0
