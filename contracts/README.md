# contracts/

These schemas are the platform-facing contract family shared by runtime services.
They are generated or curated under pinned upstream standards and references, but the materialized platform contracts live here so services can validate against one repo-local source.

The initial family is intentionally small:
- `CarrierIngested`
- `EventEnvelope`
- `MembraneDecision`
- `EvidenceReceipt`
- `TopicAssigned`
- `EmbeddingComputed`
- `LensOutput`
- `ExportApproved`
- `ExportDenied`
- `ProvableAIOpsExchange`

## Provable AI Operations Exchange

`ProvableAIOpsExchange.v0.1.json` is the higher-order artifact graph for certified intelligence and agentic operations custody. It complements `EvidenceReceipt` rather than replacing it:

- `EvidenceReceipt` is the compact runtime receipt emitted by services.
- `ProvableAIOpsExchange` assembles claims, evidence, artifacts, custody events, specialist credentials, agent actions, evaluation runs, benchmark packs, policy decisions, review attestations, and rendered intelligence briefs.

Use it when a workflow needs to replace analyst-style authority with reproducible, challengeable, policy-gated operating proof.
