# Crystal Atlas platform contracts

This directory holds platform-facing event schemas for the Crystal Atlas lane.

## Event families

### Upstream extraction and enrichment
- `enrichment.emitted.v0`
- `doc.clauses.extracted.v0`
- `doc.clauses.scored.v0`
- `entities.resolved.v0`
- `entities.resolved.crossdoc.v0`

### Downstream contract and procurement intelligence
- `contract.clauses.compared.v0`
- `procurement.substitution.recommended.v0`
- `entitlement.adjacency.inferred.v0`
- `diligence.risk.pack.generated.v0`

This initial landing is intentionally contract-first. Runtime consumers live under `apps/`.
