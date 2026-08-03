# Evidence Cover Graph — contract fixtures

Spec-as-code for **evidence sufficiency expressed as covers** (hyperedges) over
content-addressed evidence items, with overlap (gluing) constraints and disclosure tiers.

- Schema: [`schemas/evidence-cover-graph.schema.json`](../../../schemas/evidence-cover-graph.schema.json)
- Validator: [`tools/validate_evidence_cover_graph.py`](../../../tools/validate_evidence_cover_graph.py)
  (`make validate-evidence-cover-graph`)

Two verdicts per graph:

1. **ValidateGraph** (structural, checker rules C1–C5): unique evidence ids; cover
   evidence refs resolve; overlap cover refs resolve; cover `claim_id` matches the
   graph `claim_id`; tiers are in `tier_policy.tier_order`. `reject_*` fixtures are
   expected-invalid (the checker inverts pass/fail on them).
2. **Gluing gate** (`CheckOverlapConsistency`): for each overlap requirement, evidence
   items whose `<TYPE>` matches the `must_agree_on` path prefix, drawn from every
   listed cover, must agree on `.digest_sha256`; disagreement ⇒ `INCONCLUSIVE` with a
   deterministic, content-addressed `RepairRequest` (`glue_inconclusive_*` fixtures).

`event_ir` / `proof_artifact` / `analysis_config` objects from the same source bundle
are **already-real** in the estate — see `schemas/event-ir.schema.json` and
`schemas/proof-artifact.schema.json`. Only the cover/overlap/tier registry was net-new.

Canonicalization follows the platform CanonicalizationProfile (UTF-8 JSON, sorted keys,
tight separators, SHA-256). Provenance: `aht_triproof_vectors_v0_1` /
`evidence_cover_registry_spec_v0_1` (2026-07-31 spec intake).
