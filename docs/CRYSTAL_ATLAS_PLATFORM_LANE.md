# Crystal Atlas platform lane

Crystal Atlas is a platform lane inside `prophet-platform`, not a detached notebook or research pack.

## Scope

It covers:
- source document extraction and enrichment
- clause and entity normalization
- cross-document joins
- downstream contract and procurement intelligence

## Platform decomposition

### Contracts
Platform-facing event schemas live under `contracts/crystal-atlas/`.

### Apps
Deployable consumers live under `apps/`.

### Docs
Platform placement, deployment, and governance notes live under `docs/`.

## Upstream event family

- `enrichment.emitted.v0`
- `doc.clauses.extracted.v0`
- `doc.clauses.scored.v0`
- `entities.resolved.v0`
- `entities.resolved.crossdoc.v0`

## Downstream event family

- `contract.clauses.compared.v0`
- `procurement.substitution.recommended.v0`
- `entitlement.adjacency.inferred.v0`
- `diligence.risk.pack.generated.v0`

## Non-negotiables

- evidence-bearing outputs, not silent truth
- policy-bounded publication
- tenant-scoped joins by default
- stable contracts even when extractors change behind them
