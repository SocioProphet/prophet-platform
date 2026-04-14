# Crystal Atlas platform lane

This document introduces the **Crystal Atlas** extraction, enrichment, and contract-intelligence lane inside `prophet-platform`.

## Why this belongs here

`prophet-platform` is the runtime and deployment hub for platform services. Crystal Atlas is not a detached research pack. It is a platform lane that consumes source documents, emits evidence-bearing structured events, and supports downstream comparison, adjacency, and diligence workflows.

## Lane decomposition

### Upstream extraction and enrichment
Crystal Atlas upstream work produces platform-facing events such as:
- `doc.clauses.extracted.v0`
- `doc.clauses.scored.v0`
- `entities.resolved.v0`
- `entities.resolved.crossdoc.v0`
- `enrichment.emitted.v0`

These contracts are intentionally event-first and transport-neutral.

### Downstream contract intelligence
A downstream consumer turns those structured events into workflow-level intelligence:
- `contract.clauses.compared.v0`
- `procurement.substitution.recommended.v0`
- `entitlement.adjacency.inferred.v0`
- `diligence.risk.pack.generated.v0`

## Platform placement

- `contracts/crystal-atlas/` carries the platform-facing event schemas.
- `apps/crystal-atlas-contract-intel/` is the first deployable downstream consumer scaffold.
- `docs/` explains how the lane maps into runtime, deployment, and governance.

## Non-negotiables

- Claims are evidence-bearing, not silent truth.
- Contracts are stable even if extractors or scorers change behind them.
- Public/private publication remains a policy decision, not an extractor-side shortcut.
- Cross-document joins must remain tenant-scoped by default.

## Next implementation slice

1. add an app entrypoint for consuming upstream topic streams
2. bind emitted events into the platform receipt/evidence fabric
3. expose comparison and diligence endpoints through the platform gateway
