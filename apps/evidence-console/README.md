# evidence-console

Thin operator-facing surface over the platform evidence lane.

## Why it exists

The platform already has:
- producers (`eval-fabric-api`, `lampstand`)
- a reader (`evidence-receipts`)
- gateway evidence routes

`evidence-console` adds the first operator-shaped aggregation layer without introducing persistence, indexing, or cache complexity.

## Endpoints

- `/healthz`
- `/v1/console/frontier`
- `/v1/console/models/{model_release_id}`
- `/v1/console/coverage`
- `/v1/console/recent-events`
- `/console/evidence` — minimal HTML stub

## Inputs

This service reads only from `evidence-receipts`.

## Limits

- no persistence
- no background indexing
- no cache/materialized view layer
- no auth yet beyond whatever ingress layer is in front of it
