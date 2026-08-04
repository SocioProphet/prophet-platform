#!/usr/bin/env python3
"""Claim extraction + memory tiers (Workspace Control Plane, Phase 8 / D6, D13).

Scaffold-first: four memory-tier semantics — short-term recency (Letta-style),
graph-structured subject/predicate (Graphiti-style), vector-like retrieval
(GraphRAG-style, keyword TF-IDF in the scaffold), and hierarchical clustering
(HippoRAG-style, inverted-index in the scaffold) — implemented in-process with
**no ML/embedding model dependency**. Swap real models behind the same
ClaimExtractor / MemoryStore interfaces later.

Design decisions:
  D6  — Claims carry provenance, confidence, contradiction_status, and
         epistemic_level. Extraction is declared (method field); never asserted.
  D13 — Memory spans four tiers. Recency alone (T1) is insufficient for long
         context; graph structure (T2) + retrieval (T3) + hierarchy (T4)
         recover what recency loses — exactly the three-space discipline.

Conformance:
  All claim dicts produced/consumed here validate against the frozen
  claim.v0.schema.json (contracts/workspace-control-plane/schemas/).
"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from math import log
from typing import Optional


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _claim_id(subject: str, statement: str) -> str:
    h = hashlib.sha256(f"{subject}|{statement}".encode()).hexdigest()[:12]
    return f"claim-{h}"


def _make_claim(
    subject: str,
    statement: str,
    *,
    epistemic_level: str = "speculative",
    confidence: float = 0.5,
    source: str,
    method: str,
    derived_from: Optional[list[str]] = None,
    contradiction_status: str = "none",
) -> dict:
    return {
        "claim_id": _claim_id(subject, statement),
        "subject": subject,
        "statement": statement,
        "epistemic_level": epistemic_level,
        "confidence": round(confidence, 4),
        "provenance": {
            "source": source,
            "method": method,
            "collected_at": _now(),
            "derived_from": list(derived_from or []),
        },
        "contradiction_status": contradiction_status,
    }


# ── Claim extractor (scaffold: simple sentence heuristic) ────────────────────

_SENT_SEP = re.compile(r"(?<=[.!?])\s+")
_VERB_WORDS = {"is", "are", "was", "were", "has", "have", "had", "does", "do",
               "can", "will", "should", "must", "may"}


def _extract_subject(sentence: str) -> str:
    """Heuristic: first NP chunk (words before first verb)."""
    words = sentence.split()
    for i, w in enumerate(words):
        if w.lower() in _VERB_WORDS or (i > 0 and len(w) > 3 and w.endswith("s")):
            return " ".join(words[:i]) or words[0] if words else "unknown"
    return words[0] if words else "unknown"


class ClaimExtractor:
    """Extract claim.v0 records from free text.

    Scaffold: sentence-splitting + simple subject heuristic + TF-IDF confidence.
    Production: swap in an LLM claim extractor behind the same ``extract()`` interface.
    """

    def __init__(self, min_length: int = 8) -> None:
        self._min_length = min_length

    def extract(
        self,
        asset_id: str,
        text: str,
        *,
        method: str = "rule_based_v0",
        epistemic_level: str = "speculative",
    ) -> list[dict]:
        """Return claim.v0 records extracted from ``text``.

        Each sentence becomes one candidate claim. Sentences shorter than
        ``min_length`` chars are dropped (noise rejection).
        Confidence = normalised sentence length (longer = more informative in scaffold).
        """
        sentences = [s.strip() for s in _SENT_SEP.split(text) if len(s.strip()) >= self._min_length]
        if not sentences:
            return []
        max_len = max(len(s) for s in sentences)
        claims = []
        for s in sentences:
            subject = _extract_subject(s)
            conf = round(len(s) / max(max_len, 1), 4)
            claims.append(
                _make_claim(
                    subject=subject,
                    statement=s,
                    epistemic_level=epistemic_level,
                    confidence=conf,
                    source=asset_id,
                    method=method,
                )
            )
        return claims


# ── Memory tiers ─────────────────────────────────────────────────────────────

class MemoryStore:
    """Four-tier memory store over claim.v0 records.

    T1 — Short-term recency (Letta-style): last N ingested claims.
    T2 — Graph-structured (Graphiti-style): subject → [claims] index.
    T3 — Vector-like retrieval (GraphRAG scaffold): keyword TF overlap.
    T4 — Hierarchical (HippoRAG scaffold): inverted index over statement terms.

    All tiers share the same ingested claim corpus; they differ in the
    retrieval strategy. No external embedding model is required in the
    scaffold.
    """

    def __init__(self, short_term_window: int = 50) -> None:
        self._window = short_term_window
        self._recent: list[dict] = []          # T1 recency buffer
        self._by_subject: dict[str, list[dict]] = defaultdict(list)  # T2 graph
        self._inverted: dict[str, list[dict]] = defaultdict(list)    # T4 hierarchy
        self._all: list[dict] = []

    # ── Ingest ───────────────────────────────────────────────────────────────

    def ingest(self, claim: dict) -> None:
        """Add a claim.v0 dict to all tiers."""
        if not isinstance(claim.get("claim_id"), str) or not claim.get("statement"):
            raise ValueError(f"claim missing required fields: {list(claim)}")
        self._all.append(claim)

        # T1: recency buffer
        self._recent.append(claim)
        if len(self._recent) > self._window:
            self._recent.pop(0)

        # T2: subject graph
        subject = claim.get("subject", "")
        if subject:
            self._by_subject[subject].append(claim)

        # T4: inverted index (lower-cased terms from statement)
        statement = claim.get("statement", "")
        terms = set(re.findall(r"\b\w{3,}\b", statement.lower()))
        for term in terms:
            self._inverted[term].append(claim)

    def ingest_many(self, claims: list[dict]) -> None:
        for c in claims:
            self.ingest(c)

    # ── T1: Short-term recency ────────────────────────────────────────────────

    def recall_recent(self, n: int = 10) -> list[dict]:
        """Return the ``n`` most recently ingested claims."""
        return list(reversed(self._recent[-n:]))

    # ── T2: Graph-structured ──────────────────────────────────────────────────

    def recall_by_subject(self, subject: str) -> list[dict]:
        """Return all claims whose subject equals ``subject`` (exact match)."""
        return list(self._by_subject.get(subject, []))

    def recall_subjects(self) -> list[str]:
        """Return all known subject keys in the graph tier."""
        return list(self._by_subject)

    # ── T3: Vector-like retrieval (scaffold: keyword TF overlap) ─────────────

    def recall_similar(self, statement: str, *, top_k: int = 5) -> list[dict]:
        """Return the ``top_k`` claims most similar to ``statement``.

        Scaffold uses TF term overlap (no embedding model).
        Production: replace with cosine similarity over real embeddings.
        """
        query_terms = set(re.findall(r"\b\w{3,}\b", statement.lower()))
        if not query_terms:
            return []
        scored: list[tuple[float, dict]] = []
        for c in self._all:
            c_terms = set(re.findall(r"\b\w{3,}\b", c.get("statement", "").lower()))
            overlap = len(query_terms & c_terms)
            if overlap:
                idf_weight = sum(log(1 + 1 / max(len(self._inverted.get(t, [])), 1))
                                  for t in query_terms & c_terms)
                scored.append((overlap * idf_weight, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_k]]

    # ── T4: Hierarchical (HippoRAG scaffold: cluster by term) ────────────────

    def recall_by_term(self, term: str) -> list[dict]:
        """Return claims containing ``term`` (inverted-index; case-insensitive)."""
        return list(self._inverted.get(term.lower(), []))

    def cluster_summary(self) -> dict[str, int]:
        """Return a {term: count} histogram over the inverted index (T4 scaffold)."""
        return {t: len(v) for t, v in self._inverted.items()}

    # ── Contradiction management ───────────────────────────────────────────────

    def mark_contested(self, claim_id: str) -> bool:
        """Mark a claim as contested (none→contested). Returns True if found."""
        for c in self._all:
            if c.get("claim_id") == claim_id:
                if c.get("contradiction_status") == "none":
                    c["contradiction_status"] = "contested"
                return True
        return False

    def mark_superseded(self, claim_id: str, *, by_claim_id: str) -> bool:
        """Mark a claim as superseded by another claim."""
        for c in self._all:
            if c.get("claim_id") == claim_id:
                c["contradiction_status"] = "superseded"
                return True
        return False

    # ── Inspection ───────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._all)

    def all_claims(self) -> list[dict]:
        return list(self._all)
