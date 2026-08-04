"""Tests for consensus_arbitrator.py (Phase 12).

24 tests covering:
  - ConsensusDecision schema fields
  - Unique consensus_id per call
  - Quorum modes: unanimous / majority / any
  - Edge cases: empty list, single decision, all-allowed, all-blocked, exact majority
  - error decisions count as blocked
  - fail-closed on corrupt input
  - OTel span emitted as GUARDRAIL kind
  - span attributes: quorum_mode, input_count, verdict, allowed/blocked counts
  - span events: consensus.input per decision, consensus.decided
  - arbitrate() is side-effect free (same list → independent records)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from consensus_arbitrator import ConsensusArbitrator
from otel_tracer import InMemoryExporter, Tracer, SPAN_KIND_GUARDRAIL, OPENINFERENCE_SPAN_KIND


# ── helpers ───────────────────────────────────────────────────────────────────

def _exp():
    return InMemoryExporter()


def _tracer(exp=None):
    return Tracer(exporter=exp or _exp())


def _arb(mode="unanimous", exp=None):
    return ConsensusArbitrator(_tracer(exp), quorum_mode=mode)


def _dec(verdict="allowed", policy_id="p1", decision_id=None):
    import uuid
    return {
        "decision_id":   decision_id or f"pd-{uuid.uuid4().hex[:12]}",
        "policy_id":     policy_id,
        "verdict":       verdict,
        "evaluated_at":  "2026-01-01T00:00:00+00:00",
        "rules":         [],
        "evidence_refs": [],
        "error":         None,
    }


# ── schema ────────────────────────────────────────────────────────────────────

def test_schema_fields():
    r = _arb().arbitrate([_dec("allowed"), _dec("allowed")])
    for key in ("consensus_id", "quorum_mode", "verdict", "decided_at",
                "total", "allowed_count", "blocked_count", "input_decisions", "error"):
        assert key in r, f"Missing field: {key}"


def test_consensus_id_unique():
    a = _arb()
    r1 = a.arbitrate([_dec("allowed")])
    r2 = a.arbitrate([_dec("allowed")])
    assert r1["consensus_id"] != r2["consensus_id"]


def test_consensus_id_prefix():
    r = _arb().arbitrate([_dec()])
    assert r["consensus_id"].startswith("cd-")


def test_quorum_mode_in_record():
    for mode in ("unanimous", "majority", "any"):
        r = ConsensusArbitrator(_tracer(), quorum_mode=mode).arbitrate([_dec("allowed")])
        assert r["quorum_mode"] == mode


# ── unanimous ─────────────────────────────────────────────────────────────────

def test_unanimous_all_allowed():
    r = _arb("unanimous").arbitrate([_dec("allowed"), _dec("allowed"), _dec("allowed")])
    assert r["verdict"] == "allowed"


def test_unanimous_one_blocked():
    r = _arb("unanimous").arbitrate([_dec("allowed"), _dec("blocked"), _dec("allowed")])
    assert r["verdict"] == "blocked"


def test_unanimous_all_blocked():
    r = _arb("unanimous").arbitrate([_dec("blocked"), _dec("blocked")])
    assert r["verdict"] == "blocked"


# ── majority ──────────────────────────────────────────────────────────────────

def test_majority_strict_majority():
    r = _arb("majority").arbitrate([_dec("allowed"), _dec("allowed"), _dec("blocked")])
    assert r["verdict"] == "allowed"


def test_majority_exact_half_is_blocked():
    # 2-of-4 is NOT a strict majority
    r = _arb("majority").arbitrate([_dec("allowed"), _dec("allowed"),
                                     _dec("blocked"), _dec("blocked")])
    assert r["verdict"] == "blocked"


def test_majority_all_blocked():
    r = _arb("majority").arbitrate([_dec("blocked"), _dec("blocked")])
    assert r["verdict"] == "blocked"


# ── any ───────────────────────────────────────────────────────────────────────

def test_any_one_allowed():
    r = _arb("any").arbitrate([_dec("blocked"), _dec("allowed"), _dec("blocked")])
    assert r["verdict"] == "allowed"


def test_any_all_blocked():
    r = _arb("any").arbitrate([_dec("blocked"), _dec("blocked")])
    assert r["verdict"] == "blocked"


# ── edge cases ────────────────────────────────────────────────────────────────

def test_empty_list_is_blocked():
    r = _arb("unanimous").arbitrate([])
    assert r["verdict"] == "blocked"
    assert r["total"] == 0


def test_single_allowed():
    r = _arb("unanimous").arbitrate([_dec("allowed")])
    assert r["verdict"] == "allowed"


def test_error_verdict_counts_as_blocked():
    r = _arb("unanimous").arbitrate([_dec("allowed"), _dec("error")])
    assert r["verdict"] == "blocked"
    assert r["allowed_count"] == 1
    assert r["blocked_count"] == 1


def test_counts():
    decisions = [_dec("allowed"), _dec("allowed"), _dec("blocked")]
    r = _arb("majority").arbitrate(decisions)
    assert r["total"] == 3
    assert r["allowed_count"] == 2
    assert r["blocked_count"] == 1


def test_input_decisions_preserved():
    d1, d2 = _dec("allowed"), _dec("blocked")
    r = _arb("unanimous").arbitrate([d1, d2])
    assert r["input_decisions"] == [d1["decision_id"], d2["decision_id"]]


# ── OTel span ─────────────────────────────────────────────────────────────────

def test_guardrail_span_emitted():
    exp = _exp()
    _arb("unanimous", exp).arbitrate([_dec("allowed")])
    assert any(s["name"] == "consensus.arbitrate" for s in exp.spans)


def test_span_kind_guardrail():
    exp = _exp()
    _arb("unanimous", exp).arbitrate([_dec("allowed")])
    span = next(s for s in exp.spans if s["name"] == "consensus.arbitrate")
    assert span["attributes"].get(OPENINFERENCE_SPAN_KIND) == SPAN_KIND_GUARDRAIL


def test_span_attributes_present():
    exp = _exp()
    _arb("majority", exp).arbitrate([_dec("allowed"), _dec("blocked")])
    span = next(s for s in exp.spans if s["name"] == "consensus.arbitrate")
    assert span["attributes"].get("consensus.quorum_mode") == "majority"
    assert span["attributes"].get("consensus.input_count") == 2
    assert span["attributes"].get("consensus.verdict") in ("allowed", "blocked")


def test_span_events_include_inputs():
    exp = _exp()
    d1, d2 = _dec("allowed"), _dec("blocked")
    _arb("any", exp).arbitrate([d1, d2])
    span = next(s for s in exp.spans if s["name"] == "consensus.arbitrate")
    input_events = [e for e in span["events"] if e["name"] == "consensus.input"]
    assert len(input_events) == 2
    input_ids = {e["attributes"]["decision_id"] for e in input_events}
    assert d1["decision_id"] in input_ids
    assert d2["decision_id"] in input_ids


def test_decided_event():
    exp = _exp()
    _arb("unanimous", exp).arbitrate([_dec("allowed")])
    span = next(s for s in exp.spans if s["name"] == "consensus.arbitrate")
    decided = [e for e in span["events"] if e["name"] == "consensus.decided"]
    assert len(decided) == 1
    assert decided[0]["attributes"]["verdict"] in ("allowed", "blocked")


def test_fail_closed_on_non_dict_input():
    """The docstring at the top of this file has claimed 'fail-closed on corrupt input'
    coverage since the PR that introduced this module, but no test exercised a genuinely
    malformed `decisions` entry (None, a bare string — not just a dict with error set).

    `_run()` raises AttributeError on `d.get(...)` for a non-dict `d`; the except-handler
    in `arbitrate()` used to REBUILD `input_decisions` with the same `d.get(...)` over the
    same malformed list while constructing the error record, raising a second, uncaught
    AttributeError that escaped `arbitrate()` entirely — no verdict returned, not even
    'blocked'. That is not fail-closed, it's a crash. This asserts the real contract: any
    exception during arbitration — including a malformed input list — still yields a
    `blocked` ConsensusDecision, never an unhandled exception."""
    good = _dec("allowed")
    result = _arb("any").arbitrate([good, None, "not-a-decision"])
    assert result["verdict"] == "blocked"
    assert result["error"]
    assert result["total"] == 3
    assert result["input_decisions"] == [good["decision_id"], "", ""]


def test_side_effect_free():
    decisions = [_dec("allowed"), _dec("blocked")]
    a = _arb("majority")
    r1 = a.arbitrate(decisions)
    r2 = a.arbitrate(decisions)
    assert r1["consensus_id"] != r2["consensus_id"]
    assert r1["input_decisions"] == r2["input_decisions"]
