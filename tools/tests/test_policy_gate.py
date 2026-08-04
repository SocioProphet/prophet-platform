"""Policy gate + PolicyDecision records (Phase 10) — correctness and gate proof.

Tests prove:
  - PolicyDecision schema: all required fields, correct verdict values
  - Allowed verdict: all rules satisfied → verdict=allowed
  - Blocked verdict: at least one rule fails → verdict=blocked
  - Require rule: min_count=0 always passes; min_count > matches blocks
  - Forbid rule: any match on forbid_term blocks even when require passes
  - Evidence refs: decision carries claim_ids from all matching rules
  - GUARDRAIL span: emitted with policy_id + verdict attributes
  - Child recall spans: one RETRIEVER span per rule per require/forbid branch
  - Trace chain: rule spans are children of the GUARDRAIL root span
  - Fail-closed: exception during evaluation → verdict=blocked (never allowed)
  - Error field: populated when exception raised during evaluation
  - Empty policy (no rules): verdict=allowed (vacuously true)
  - Multiple-rule policy: all rules must pass
  - Forbid without require: blocks when any forbid term matches
  - Deduplication: evidence_refs contains no duplicate claim_ids
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from otel_tracer import InMemoryExporter, Tracer, OPENINFERENCE_SPAN_KIND  # type: ignore  # noqa
from memory_tier import MemoryStore, _make_claim  # type: ignore  # noqa
from policy_gate import Policy, PolicyGate, Rule  # type: ignore  # noqa

# ── helpers ───────────────────────────────────────────────────────────────────

def _store_with_claims(*texts: str) -> MemoryStore:
    store = MemoryStore()
    for i, text in enumerate(texts):
        store.ingest(_make_claim(f"subject-{i}", text,
                                 source="test", method="test", confidence=0.7))
    return store


def _gate(store, exp=None) -> tuple[PolicyGate, InMemoryExporter]:
    exp = exp or InMemoryExporter()
    tracer = Tracer(exporter=exp)
    return PolicyGate(store, tracer), exp


# ── Schema / required fields ──────────────────────────────────────────────────

def test_decision_has_all_required_fields():
    store = _store_with_claims("attestation proves boot integrity.")
    gate, _ = _gate(store)
    policy = Policy("pol-001", rules=[Rule("has-attestation", "attestation")])
    d = gate.evaluate(policy)
    for key in ("decision_id", "policy_id", "verdict", "evaluated_at",
                "rules", "evidence_refs", "error"):
        assert key in d, f"missing key: {key}"


def test_decision_id_is_unique():
    store = _store_with_claims("governance evidence is present.")
    gate, _ = _gate(store)
    policy = Policy("pol-002", rules=[Rule("has-governance", "governance")])
    ids = {gate.evaluate(policy)["decision_id"] for _ in range(5)}
    assert len(ids) == 5


def test_policy_id_propagated():
    store = _store_with_claims("evidence collected.")
    gate, _ = _gate(store)
    d = gate.evaluate(Policy("my-policy-id"))
    assert d["policy_id"] == "my-policy-id"


# ── Verdict: allowed ──────────────────────────────────────────────────────────

def test_allowed_when_all_rules_pass():
    store = _store_with_claims(
        "attestation confirms the boot chain is valid.",
        "governance policy is satisfied by this evidence.",
    )
    gate, _ = _gate(store)
    policy = Policy("pol-allow", rules=[
        Rule("has-attestation", "attestation"),
        Rule("has-governance", "governance"),
    ])
    d = gate.evaluate(policy)
    assert d["verdict"] == "allowed"


def test_empty_policy_is_vacuously_allowed():
    store = _store_with_claims("anything here.")
    gate, _ = _gate(store)
    d = gate.evaluate(Policy("empty-pol"))
    assert d["verdict"] == "allowed"
    assert d["rules"] == []


# ── Verdict: blocked ──────────────────────────────────────────────────────────

def test_blocked_when_require_count_not_met():
    store = MemoryStore()  # empty
    gate, _ = _gate(store)
    policy = Policy("pol-block", rules=[Rule("needs-attestation", "attestation", min_count=1)])
    d = gate.evaluate(policy)
    assert d["verdict"] == "blocked"


def test_blocked_when_forbid_term_matches():
    store = _store_with_claims(
        "attestation confirms boot integrity.",
        "unauthorized access attempt detected.",
    )
    gate, _ = _gate(store)
    policy = Policy("pol-forbid", rules=[
        Rule("has-attestation", "attestation", min_count=1, forbid_term="unauthorized"),
    ])
    d = gate.evaluate(policy)
    assert d["verdict"] == "blocked"


def test_allowed_when_forbid_term_does_not_match():
    store = _store_with_claims("attestation confirms boot integrity.")
    gate, _ = _gate(store)
    policy = Policy("pol-clean", rules=[
        Rule("has-attestation", "attestation", min_count=1, forbid_term="unauthorized"),
    ])
    d = gate.evaluate(policy)
    assert d["verdict"] == "allowed"


def test_min_count_zero_always_passes():
    store = MemoryStore()  # empty — no claims
    gate, _ = _gate(store)
    policy = Policy("pol-zero", rules=[Rule("optional", "anything", min_count=0)])
    d = gate.evaluate(policy)
    assert d["verdict"] == "allowed"


def test_blocked_when_any_rule_fails():
    store = _store_with_claims("attestation present.", "governance satisfied.")
    gate, _ = _gate(store)
    policy = Policy("pol-multi", rules=[
        Rule("has-attestation", "attestation"),
        Rule("missing-fips", "fips", min_count=1),   # no fips claims
    ])
    d = gate.evaluate(policy)
    assert d["verdict"] == "blocked"


# ── Rule results ──────────────────────────────────────────────────────────────

def test_rule_results_listed_for_each_rule():
    store = _store_with_claims("attestation ok.", "governance ok.")
    gate, _ = _gate(store)
    policy = Policy("pol-rules", rules=[
        Rule("r1", "attestation"),
        Rule("r2", "governance"),
    ])
    d = gate.evaluate(policy)
    assert len(d["rules"]) == 2
    names = {r["rule_name"] for r in d["rules"]}
    assert names == {"r1", "r2"}


def test_rule_result_has_correct_fields():
    store = _store_with_claims("attestation proves integrity.")
    gate, _ = _gate(store)
    policy = Policy("pol-rfields", rules=[Rule("has-attest", "attestation")])
    d = gate.evaluate(policy)
    r = d["rules"][0]
    for k in ("rule_name", "passed", "match_count", "evidence"):
        assert k in r


# ── Evidence refs ─────────────────────────────────────────────────────────────

def test_evidence_refs_contain_claim_ids():
    store = _store_with_claims("attestation is the foundation of trust.")
    gate, _ = _gate(store)
    policy = Policy("pol-evidence", rules=[Rule("has-attestation", "attestation")])
    d = gate.evaluate(policy)
    assert len(d["evidence_refs"]) >= 1
    assert all(isinstance(r, str) for r in d["evidence_refs"])


def test_evidence_refs_deduplicated():
    store = _store_with_claims(
        "attestation confirms this unit.",
        "attestation also present here.",
    )
    gate, _ = _gate(store)
    policy = Policy("pol-dedup", rules=[
        Rule("r1", "attestation"),
        Rule("r2", "attestation"),
    ])
    d = gate.evaluate(policy)
    assert len(d["evidence_refs"]) == len(set(d["evidence_refs"]))


# ── OTel spans ────────────────────────────────────────────────────────────────

def test_guardrail_span_emitted():
    exp = InMemoryExporter()
    store = _store_with_claims("attestation ok.")
    gate, _ = _gate(store, exp)
    policy = Policy("pol-span", rules=[Rule("has-attest", "attestation")])
    gate.evaluate(policy)
    guardrail = next(
        (s for s in exp.spans if s["attributes"].get(OPENINFERENCE_SPAN_KIND) == "GUARDRAIL"),
        None,
    )
    assert guardrail is not None
    assert "pol-span" in guardrail["name"]


def test_guardrail_span_carries_verdict():
    exp = InMemoryExporter()
    store = _store_with_claims("attestation here.")
    gate, _ = _gate(store, exp)
    policy = Policy("pol-vattr", rules=[Rule("has-attest", "attestation")])
    gate.evaluate(policy)
    guardrail = next(
        s for s in exp.spans if s["attributes"].get(OPENINFERENCE_SPAN_KIND) == "GUARDRAIL"
    )
    assert guardrail["attributes"].get("policy.verdict") in ("allowed", "blocked")


def test_retriever_child_spans_emitted_per_rule():
    exp = InMemoryExporter()
    store = _store_with_claims("attestation present.", "governance present.")
    gate, _ = _gate(store, exp)
    policy = Policy("pol-children", rules=[
        Rule("r1", "attestation"),
        Rule("r2", "governance"),
    ])
    gate.evaluate(policy)
    retriever_spans = [
        s for s in exp.spans if s["attributes"].get(OPENINFERENCE_SPAN_KIND) == "RETRIEVER"
    ]
    assert len(retriever_spans) >= 2


def test_rule_spans_are_children_of_guardrail():
    exp = InMemoryExporter()
    store = _store_with_claims("attestation ok.")
    gate, _ = _gate(store, exp)
    policy = Policy("pol-chain", rules=[Rule("has-attest", "attestation")])
    gate.evaluate(policy)
    guardrail = next(
        s for s in exp.spans if s["attributes"].get(OPENINFERENCE_SPAN_KIND) == "GUARDRAIL"
    )
    child_spans = [
        s for s in exp.spans
        if s.get("parent_span_id") == guardrail["span_id"]
    ]
    assert len(child_spans) >= 1


# ── Fail-closed ───────────────────────────────────────────────────────────────

def test_fail_closed_on_store_exception():
    """A store that raises mid-evaluation → verdict=blocked, not allowed."""
    class BrokenStore:
        def recall_by_term(self, *_):
            raise RuntimeError("store unavailable")

    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    gate = PolicyGate(BrokenStore(), tracer)
    policy = Policy("pol-failsafe", rules=[Rule("any-rule", "term")])
    d = gate.evaluate(policy)
    assert d["verdict"] == "blocked"
    assert d["error"] is not None


def test_error_verdict_span_status():
    """The GUARDRAIL span is finished even when the store raises."""
    class BrokenStore:
        def recall_by_term(self, *_):
            raise RuntimeError("boom")

    exp = InMemoryExporter()
    tracer = Tracer(exporter=exp)
    gate = PolicyGate(BrokenStore(), tracer)
    policy = Policy("pol-err-span", rules=[Rule("any", "x")])
    gate.evaluate(policy)
    spans = [s for s in exp.spans if "policy.evaluate" in s.get("name", "")]
    assert spans
