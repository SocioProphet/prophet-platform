# Storage Promotion Slice

This is a bounded vertical slice aligned with Prophet Platform conventions.

It demonstrates:

- Observation ingest
- Promotion to semantic Claim
- Projection to graph form

## Contract alignment

Uses contracts from:
- `contracts/storage/`

## Outputs

- Promotion results (entities + claims)
- Projection manifest

## Rule

This slice is NOT a canonical truth store.
It demonstrates the governed transformation pipeline only.

## Next steps

- implement ingest command
- implement promote command
- implement project command
- integrate with receipt emission
