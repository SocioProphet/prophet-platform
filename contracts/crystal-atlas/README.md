# Crystal Atlas platform contracts

This directory holds the **platform-facing event schemas** for the Crystal Atlas lane.

## Scope

The contracts here represent:
- upstream extraction/enrichment outputs
- downstream contract/procurement intelligence outputs

These schemas are intended to be consumed by runtime services in `apps/` and validated by helpers in `tools/`.

## Event families

### Upstream
- `doc.clauses.extracted.v0`
- `doc.clauses.scored.v0`
- `entities.resolved.v0`
- `entities.resolved.crossdoc.v0`
- `enrichment.emitted.v0`

### Downstream
- `contract.clauses.compared.v0`
- `procurement.substitution.recommended.v0`
- `entitlement.adjacency.inferred.v0`
- `diligence.risk.pack.generated.v0`

## Notes

This initial landing is intentionally contract-first. Runtime bindings and deployable services are introduced incrementally under `apps/`.
