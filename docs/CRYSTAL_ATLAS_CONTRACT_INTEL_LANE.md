# Crystal Atlas contract-intelligence lane

This lane consumes structured Crystal Atlas extraction/enrichment outputs and produces workflow-level intelligence for contract review, procurement substitution, entitlement adjacency, and diligence summaries.

## Intended input contracts

The downstream lane is expected to consume:
- `doc.clauses.extracted.v0`
- `doc.clauses.scored.v0`
- `entities.resolved.v0`
- `entities.resolved.crossdoc.v0`
- `enrichment.emitted.v0`

## Output contracts

The lane emits:
- `contract.clauses.compared.v0`
- `procurement.substitution.recommended.v0`
- `entitlement.adjacency.inferred.v0`
- `diligence.risk.pack.generated.v0`

## Workflow packs

### Contract review diff
Normalizes clause families, computes deltas, and highlights missing or changed coverage.

### Procurement substitution
Ranks alternatives using preference, price, and category compatibility.

### Entitlement adjacency
Builds explainable graph edges from accounts, companies, products, and contracts.

### Diligence risk pack
Summarizes missing or weak coverage across critical clause families such as termination, audit, assignment, confidentiality, and limitation of liability.

## Why this is platform work

The lane depends on:
- stable event contracts
- provenance/evidence discipline
- replayability
- receipt emission
- deployment/runtime integration

That makes it a platform concern, not a one-off notebook or analysis pack.
