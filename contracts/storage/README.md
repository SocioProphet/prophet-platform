# contracts/storage/

This family defines the bounded storage-facing contracts used by the storage promotion slice.

These contracts do not replace the platform contract spine. They complement it.

## Purpose

The storage slice demonstrates the governed path:

1. Observation is captured as operational state.
2. Promotion derives semantic objects deterministically.
3. Projection emits a read-optimized graph shape.
4. Promotion and projection can emit repo-native receipts and envelopes later.

## Initial contract set

- `Observation.v0.1.json`
- `RunRecord.v0.1.json`
- `ProjectionManifest.v0.1.json`
- `PromotionRejection.v0.1.json`
- `PromotionReceipt.v0.1.json`

## Ownership

- Operational / branchable state: Dolt-oriented
- Semantic truth: TypeDB-oriented
- Read projection: Neo4j-shaped and derived only

## Rule

Storage contracts must remain replayable, deterministic, and traceable back to source observations.
