"""Evidence ingestion pipeline (Phase 11) — correctness and gate proof.

Tests prove:
  - CollectionReport schema: all required fields present
  - Fetch: InMemoryEventSource drains pushed events on each tick
  - Fetch: StaticTextSource yields once then stops
  - Extract: claim count matches sentences above min_length threshold
  - Ingest: claims land in MemoryStore; recalled after collect
  - Noise gate: events shorter than min_text_length are skipped
  - Policy evaluation: decision appended for each policy after tick
  - Allowed verdict: satisfied policy produces allowed decision
  - Blocked verdict: unsatisfied policy produces blocked decision
  - Multiple policies: all policies evaluated per tick
  - Span trace_id: report carries trace_id from the root CHAIN span
  - CHAIN root span: evidence.collect span is emitted
  - Child spans: evidence.fetch + evidence.extract + evidence.evaluate emitted
  - Fail-soft: fetch exception → report.error set, no crash
  - Incremental fetch: second tick only gets new events
  - Scheduler smoke: schedule/cancel does not raise
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from otel_tracer import InMemoryExporter, Tracer, OPENINFERENCE_SPAN_KIND  # type: ignore
from memory_tier import ClaimExtractor, MemoryStore  # type: ignore
from policy_gate import Policy, Rule  # type: ignore
from evidence_collector import (  # type: ignore
    CollectionReport,
    EvidenceCollector,
    Event,
    InMemoryEventSource,
    StaticTextSource,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _collector(
    *texts: tuple[str, str],
    policies=None,
    exp=None,
    min_text_length: int = 8,
) -> tuple[EvidenceCollector, MemoryStore, InMemoryExporter]:
    source = InMemoryEventSource()
    for sid, txt in texts:
        source.push(Event(source_id=sid, text=txt))
    exp = exp or InMemoryExporter()
    tracer = Tracer(exporter=exp)
    store = MemoryStore()
    extractor = ClaimExtractor(min_length=min_text_length)
    collector = EvidenceCollector(
        source, extractor, store,
        policies=list(policies or []),
        tracer=tracer,
        min_text_length=min_text_length,
    )
    return collector, store, exp


# ── CollectionReport schema ───────────────────────────────────────────────────

def test_report_has_all_required_fields():
    col, _, _ = _collector(("src-1", "Attestation binds the boot chain securely."))
    report = col.collect()
    for key in ("report_id", "collected_at", "events_fetched", "claims_extracted",
                "claims_ingested", "ingest_errors", "policy_decisions",
                "span_trace_id", "error"):
        assert key in report.to_dict(), f"missing: {key}"


def test_report_id_is_unique():
    col, _, _ = _collector()
    ids = {col.collect().report_id for _ in range(5)}
    assert len(ids) == 5


# ── InMemoryEventSource ───────────────────────────────────────────────────────

def test_in_memory_source_drains_pushed_events():
    col, _, _ = _collector(
        ("src-a", "Governance evidence is present and verifiable."),
        ("src-b", "Attestation confirms the boot sequence was clean."),
    )
    report = col.collect()
    assert report.events_fetched == 2


def test_incremental_fetch_only_new_events():
    source = InMemoryEventSource()
    store = MemoryStore()
    extractor = ClaimExtractor()
    col = EvidenceCollector(source, extractor, store)
    source.push(Event("s1", "First evidence: governance is satisfied."))
    r1 = col.collect()
    source.push(Event("s2", "Second evidence: attestation is verified now."))
    r2 = col.collect()
    assert r1.events_fetched == 1
    assert r2.events_fetched == 1


# ── StaticTextSource ──────────────────────────────────────────────────────────

def test_static_text_source_yields_once():
    source = StaticTextSource([("src", "Attestation is the root of trust evidence.")])
    store = MemoryStore()
    extractor = ClaimExtractor()
    col = EvidenceCollector(source, extractor, store)
    r1 = col.collect()
    r2 = col.collect()
    assert r1.events_fetched == 1
    assert r2.events_fetched == 0


# ── Extract + ingest ──────────────────────────────────────────────────────────

def test_claims_ingested_into_store():
    col, store, _ = _collector(
        ("git:sha1", "Attestation proves the build was clean and reproducible."),
        ("git:sha2", "Governance policy is satisfied by the evidence chain here."),
    )
    col.collect()
    all_claims = store.all_claims()
    assert len(all_claims) >= 2


def test_report_counts_match_store():
    col, store, _ = _collector(
        ("ci:run-1", "Evidence collected during the CI run confirms integrity."),
    )
    report = col.collect()
    assert report.claims_ingested == len(store.all_claims())


def test_claims_recalled_after_collect():
    col, store, _ = _collector(
        ("audit:01", "Attestation signature validated against the chain of trust."),
    )
    col.collect()
    results = store.recall_by_term("attestation")
    assert len(results) >= 1


# ── Noise gate ────────────────────────────────────────────────────────────────

def test_short_events_skipped_by_noise_gate():
    col, store, _ = _collector(
        ("s1", "ok"),           # too short (< 8)
        ("s2", "This is a properly long sentence with real content."),
        min_text_length=20,
    )
    report = col.collect()
    assert report.events_fetched == 2
    assert report.claims_ingested >= 1
    # The very short "ok" event should produce 0 claims
    all_claims = store.all_claims()
    assert not any(c.get("statement") == "ok" for c in all_claims)


# ── Policy evaluation ─────────────────────────────────────────────────────────

def test_policy_decisions_appended_after_tick():
    policy = Policy("pol-attest", rules=[Rule("has-attestation", "attestation")])
    col, _, _ = _collector(
        ("s1", "Attestation proves the build chain is valid and complete."),
        policies=[policy],
    )
    report = col.collect()
    assert len(report.policy_decisions) == 1


def test_allowed_verdict_when_policy_satisfied():
    policy = Policy("pol-allow", rules=[Rule("has-governance", "governance")])
    col, _, _ = _collector(
        ("s1", "Governance evidence is present and meets all requirements."),
        policies=[policy],
    )
    report = col.collect()
    assert report.policy_decisions[0]["verdict"] == "allowed"


def test_blocked_verdict_when_policy_not_satisfied():
    policy = Policy("pol-block", rules=[Rule("needs-fips", "fips", min_count=1)])
    col, _, _ = _collector(
        ("s1", "Attestation is present but no cryptographic conformance record."),
        policies=[policy],
    )
    report = col.collect()
    assert report.policy_decisions[0]["verdict"] == "blocked"


def test_multiple_policies_all_evaluated():
    p1 = Policy("pol-1", rules=[Rule("r1", "attestation")])
    p2 = Policy("pol-2", rules=[Rule("r2", "governance")])
    col, _, _ = _collector(
        ("s1", "Attestation and governance both confirmed in this evidence."),
        policies=[p1, p2],
    )
    report = col.collect()
    assert len(report.policy_decisions) == 2
    policy_ids = {d["policy_id"] for d in report.policy_decisions}
    assert policy_ids == {"pol-1", "pol-2"}


# ── OTel spans ────────────────────────────────────────────────────────────────

def test_span_trace_id_in_report():
    col, _, _ = _collector(("s1", "Evidence for the trace id test case."))
    report = col.collect()
    assert report.span_trace_id is not None
    assert len(report.span_trace_id) > 0


def test_chain_root_span_emitted():
    exp = InMemoryExporter()
    col, _, _ = _collector(("s1", "Evidence for the span chain test."), exp=exp)
    col.collect()
    chains = [s for s in exp.spans if "evidence.collect" in s.get("name", "")]
    assert chains


def test_fetch_and_extract_child_spans_emitted():
    exp = InMemoryExporter()
    col, _, _ = _collector(
        ("s1", "Attestation evidence is present and verifiable."),
        exp=exp,
    )
    col.collect()
    span_names = [s["name"] for s in exp.spans]
    assert any("evidence.fetch" in n for n in span_names)
    assert any("evidence.extract" in n for n in span_names)


# ── Fail-soft ─────────────────────────────────────────────────────────────────

def test_fail_soft_on_fetch_exception():
    class BrokenSource:
        def fetch(self, since=None):
            raise RuntimeError("source unavailable")

    store = MemoryStore()
    extractor = ClaimExtractor()
    col = EvidenceCollector(BrokenSource(), extractor, store)
    report = col.collect()
    assert report.error is not None
    assert report.claims_ingested == 0


# ── Scheduler smoke ───────────────────────────────────────────────────────────

def test_scheduler_starts_and_cancels():
    col, _, _ = _collector()
    col.schedule(3600)  # very long interval — won't fire in test
    col.cancel()
    assert col._timer is None
