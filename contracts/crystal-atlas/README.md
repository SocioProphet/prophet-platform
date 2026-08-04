# Crystal Atlas platform contracts

This directory holds the **platform-facing event schemas** for the Crystal Atlas lane.

## Scope

The contracts here represent:
- upstream extraction/enrichment outputs
- downstream contract/procurement intelligence outputs

These schemas are intended to be consumed by runtime services in `apps/` and validated by helpers in `tools/`.

## Event families

Everything listed below without a marker **ships as a schema in `events/`**. Entries
marked _(planned)_ are intent, not contract — they have no schema and nothing may be
built against them. `tools/tests/test_crystal_atlas_event_register.py` holds this list
to what is actually in `events/`, in both directions, so it cannot drift again.

### Upstream
- `doc.clauses.extracted.v0`
- `enrichment.emitted.v0`
- `catalog.resolved.v0`
- `catalog.dcat.emitted.v0`
- `catalog.ops.readout.v0`
- `catalog.ops.slo.v0`
- `doc.clauses.scored.v0` _(planned)_
- `entities.resolved.v0` _(planned)_
- `entities.resolved.crossdoc.v0` _(planned)_

### Downstream
- `contract.clauses.compared.v0`
- `procurement.substitution.recommended.v0`
- `entitlement.adjacency.inferred.v0`
- `diligence.risk.pack.generated.v0`
- `intel.value_driver.scored.v0`

## Notes

This initial landing is intentionally contract-first. Runtime bindings and deployable services are introduced incrementally under `apps/`.
