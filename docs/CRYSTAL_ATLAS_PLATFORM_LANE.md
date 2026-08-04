# Crystal Atlas platform lane

This document introduces the **Crystal Atlas** extraction, enrichment, and contract-intelligence lane inside `prophet-platform`.

## Why this belongs here

`prophet-platform` is the runtime and deployment hub for platform services. Crystal Atlas is not a detached research pack. It is a platform lane that consumes source documents, emits evidence-bearing structured events, and supports downstream comparison, adjacency, and diligence workflows.

## Lane decomposition

### Upstream extraction and enrichment
### Downstream contract intelligence

The authoritative list of event families lives in `contracts/crystal-atlas/README.md`
and is held to the shipped schemas, in both directions, by
`tools/tests/test_crystal_atlas_event_register.py`.

It is deliberately not duplicated here. This document previously carried its own copy,
and both copies drifted: three families were named with no schema behind them while
five shipped schemas went unmentioned. Two registers means the one you happen to read
is a coin flip.

These contracts are event-first and transport-neutral.

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
