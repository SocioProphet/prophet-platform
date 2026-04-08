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
