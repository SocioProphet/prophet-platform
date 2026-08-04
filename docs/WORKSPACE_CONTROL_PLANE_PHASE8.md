# Workspace Control Plane — Phase 8 (claim extraction + memory tiers)

Implements **Phase 8**: claim extraction from assets and a four-tier memory
store over `claim.v0` records, scaffold-first. The Letta/Graphiti/GraphRAG/
HippoRAG **semantics** are implemented in-process with **no ML or embedding
model dependency**; swap real models behind the same `ClaimExtractor` /
`MemoryStore` interfaces later.

## Design decisions (D6 / D13)

- **D6** — Claims carry provenance (`source`, `method`, `collected_at`,
  `derived_from`), `confidence`, `contradiction_status`, and `epistemic_level`.
  Extraction is declared (method field); never asserted as ground truth.
- **D13** — Memory spans four tiers. Recency alone (T1) is insufficient for
  long context; graph structure (T2) + retrieval (T3) + hierarchy (T4)
  recover what recency loses — the three-space reconstruction discipline applied
  to live workspace memory.

## Memory tier semantics

| Tier | Name        | Scaffold impl          | Production impl     |
|------|-------------|------------------------|---------------------|
| T1   | Short-term  | Recency window (deque) | Letta working set   |
| T2   | Graph       | Subject → claims dict  | Graphiti graph      |
| T3   | Vector      | TF keyword overlap     | GraphRAG embeddings |
| T4   | Hierarchical| Inverted index (terms) | HippoRAG clusters   |

## Key classes

- **`ClaimExtractor`** — `extract(asset_id, text) → list[claim.v0]`. Scaffold:
  sentence splitting + subject heuristic + normalised-length confidence.
  Swappable: replace with an LLM claim extractor behind the same interface.
- **`MemoryStore`** — ingests claim.v0 records and exposes four recall methods:
  `recall_recent(n)` (T1), `recall_by_subject(subject)` (T2),
  `recall_similar(statement, top_k)` (T3), `recall_by_term(term)` (T4).
  Also: `mark_contested()`, `mark_superseded()` for contradiction management.
- Fail-closed: `ingest()` raises `ValueError` on malformed claims.

## Validation

`tools/tests/test_memory_tier.py` — 17 tests covering extractor conformance,
noise gate (min_length), normalised confidence, provenance, all four memory
tiers, contradiction management, and fail-closed ingest.

Path-filtered CI: `.github/workflows/control-plane-phase8.yml`.

## Next (Phase 9)

OTel / OpenInference / Phoenix observability layer over workflow-run + claim
events (structured spans, evidence traces, policy decision records).
