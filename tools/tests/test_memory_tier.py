"""Claim extraction + memory tiers (Phase 8) — correctness and gate proof.

Tests prove:
  - ClaimExtractor: produces claim.v0-conformant records from free text
  - ClaimExtractor: drops noise (short sentences); confidence is normalised
  - MemoryStore T1: recall_recent returns last N claims
  - MemoryStore T2: recall_by_subject returns exact subject matches
  - MemoryStore T3: recall_similar returns claims with highest term overlap
  - MemoryStore T4: recall_by_term inverted index + cluster_summary
  - Contradiction management: mark_contested / mark_superseded
  - Schema conformance: every extracted claim validates against claim.v0
  - Ingesting a malformed claim raises ValueError (fail-closed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from memory_tier import ClaimExtractor, MemoryStore, _make_claim  # type: ignore  # noqa: E402

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "workspace-control-plane"
    / "schemas"
    / "claim.v0.schema.json"
)


def _validator() -> Draft202012Validator | None:
    if not SCHEMA_PATH.exists():
        return None
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_VALIDATOR = _validator()


def _validate(claim: dict) -> None:
    if _VALIDATOR is not None:
        errs = list(_VALIDATOR.iter_errors(claim))
        assert not errs, "\n".join(str(e) for e in errs)


# ── ClaimExtractor ────────────────────────────────────────────────────────────

def test_extractor_produces_conformant_claims():
    """Every extracted claim must validate against claim.v0."""
    ex = ClaimExtractor()
    claims = ex.extract("doc-1", "The sky is blue. Water is wet. Birds fly south.")
    assert len(claims) >= 2
    for c in claims:
        _validate(c)


def test_extractor_drops_short_sentences():
    """Sentences below min_length are dropped (noise gate)."""
    ex = ClaimExtractor(min_length=20)
    claims = ex.extract("doc-2", "Hi. This is a short sentence. This one is definitely long enough to pass.")
    assert all(len(c["statement"]) >= 20 for c in claims)


def test_extractor_confidence_is_normalised():
    """Confidence is in [0, 1]; the longest sentence gets the highest confidence."""
    ex = ClaimExtractor()
    text = "Short sentence here. This is a substantially longer sentence that should score higher."
    claims = ex.extract("doc-3", text)
    assert all(0.0 <= c["confidence"] <= 1.0 for c in claims)
    max_conf = max(c["confidence"] for c in claims)
    assert max_conf == 1.0


def test_extractor_provenance_carries_asset_and_method():
    ex = ClaimExtractor()
    claims = ex.extract("doc-4", "Evidence-based medicine requires controlled trials.",
                        method="rule_based_v0")
    assert all(c["provenance"]["source"] == "doc-4" for c in claims)
    assert all(c["provenance"]["method"] == "rule_based_v0" for c in claims)


def test_extractor_empty_text_returns_empty_list():
    ex = ClaimExtractor()
    claims = ex.extract("doc-5", "")
    assert claims == []


# ── MemoryStore T1: short-term recency ───────────────────────────────────────

def test_recall_recent_returns_last_n():
    store = MemoryStore(short_term_window=5)
    for i in range(7):
        store.ingest(_make_claim(f"subj-{i}", f"Claim {i} is about topic {i}.",
                                 source=f"doc-{i}", method="test", confidence=0.6))
    recent = store.recall_recent(3)
    assert len(recent) == 3
    assert recent[0]["statement"].startswith("Claim 6")


def test_short_term_window_evicts_old_claims():
    store = MemoryStore(short_term_window=3)
    for i in range(5):
        store.ingest(_make_claim(f"s", f"Statement number {i} is ingested.",
                                 source="doc", method="test", confidence=0.5))
    recent = store.recall_recent(10)
    assert len(recent) == 3


# ── MemoryStore T2: graph-structured subject retrieval ────────────────────────

def test_recall_by_subject_returns_matching_claims():
    store = MemoryStore()
    store.ingest(_make_claim("Prophet Platform", "It supports multi-tenant graphs.",
                             source="doc", method="test", confidence=0.8))
    store.ingest(_make_claim("Prophet Platform", "It runs on GKE.",
                             source="doc", method="test", confidence=0.7))
    store.ingest(_make_claim("Other System", "Unrelated claim here.",
                             source="doc", method="test", confidence=0.5))
    results = store.recall_by_subject("Prophet Platform")
    assert len(results) == 2
    assert all(c["subject"] == "Prophet Platform" for c in results)


def test_recall_subjects_enumerates_graph():
    store = MemoryStore()
    for subj in ["Alpha", "Beta", "Gamma"]:
        store.ingest(_make_claim(subj, f"{subj} has a well-known property.",
                                 source="doc", method="test", confidence=0.5))
    subjects = store.recall_subjects()
    assert set(subjects) >= {"Alpha", "Beta", "Gamma"}


# ── MemoryStore T3: vector-like retrieval ─────────────────────────────────────

def test_recall_similar_returns_topk():
    store = MemoryStore()
    ex = ClaimExtractor()
    corpus = [
        "GraphRAG connects graph retrieval with language models for better recall.",
        "HippoRAG uses hierarchical indexing to improve long-context memory.",
        "Letta provides short-term recency windows for conversational agents.",
        "FIPS compliance requires approved cryptographic algorithms in federal systems.",
    ]
    for i, text in enumerate(corpus):
        store.ingest(_make_claim(f"s{i}", text, source=f"doc-{i}", method="test",
                                 confidence=0.7))

    results = store.recall_similar("graph retrieval and memory systems", top_k=2)
    assert len(results) == 2
    texts = [r["statement"] for r in results]
    assert any("graph" in t.lower() or "memory" in t.lower() for t in texts)


def test_recall_similar_empty_query_returns_empty():
    store = MemoryStore()
    store.ingest(_make_claim("s", "Something relevant.", source="doc", method="test",
                             confidence=0.5))
    results = store.recall_similar("", top_k=5)
    assert results == []


# ── MemoryStore T4: hierarchical inverted index ───────────────────────────────

def test_recall_by_term_returns_matching_claims():
    store = MemoryStore()
    store.ingest(_make_claim("s1", "Sovereign deployment uses cryptographic attestation.",
                             source="doc", method="test", confidence=0.7))
    store.ingest(_make_claim("s2", "Attestation binds the boot chain to the registry.",
                             source="doc", method="test", confidence=0.7))
    store.ingest(_make_claim("s3", "Unrelated topic about weather forecasting.",
                             source="doc", method="test", confidence=0.5))
    results = store.recall_by_term("attestation")
    assert len(results) >= 2


def test_cluster_summary_histogram():
    store = MemoryStore()
    for i in range(3):
        store.ingest(_make_claim(f"s{i}", f"Governance policy requires auditable evidence.",
                                 source="doc", method="test", confidence=0.6))
    summary = store.cluster_summary()
    assert "governance" in summary or "auditable" in summary or "evidence" in summary
    assert all(isinstance(v, int) for v in summary.values())


# ── Contradiction management ──────────────────────────────────────────────────

def test_mark_contested_transitions_none_to_contested():
    store = MemoryStore()
    claim = _make_claim("s", "Water boils at 100C at sea level.",
                        source="doc", method="test", confidence=0.9)
    store.ingest(claim)
    found = store.mark_contested(claim["claim_id"])
    assert found is True
    results = store.recall_by_subject("s")
    assert results[0]["contradiction_status"] == "contested"


def test_mark_contested_unknown_claim_id_returns_false():
    store = MemoryStore()
    assert store.mark_contested("claim-nonexistent") is False


def test_mark_superseded():
    store = MemoryStore()
    old = _make_claim("s", "Old claim about something.", source="doc", method="test",
                      confidence=0.5)
    new_c = _make_claim("s", "Improved claim about something more precise.",
                        source="doc", method="test", confidence=0.8)
    store.ingest(old)
    store.ingest(new_c)
    store.mark_superseded(old["claim_id"], by_claim_id=new_c["claim_id"])
    results = store.recall_by_subject("s")
    superseded = next(r for r in results if r["claim_id"] == old["claim_id"])
    assert superseded["contradiction_status"] == "superseded"


# ── Fail-closed ingest ────────────────────────────────────────────────────────

def test_ingest_malformed_claim_raises():
    store = MemoryStore()
    with pytest.raises(ValueError):
        store.ingest({"not_a_claim": True})
