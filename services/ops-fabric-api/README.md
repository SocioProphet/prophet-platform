# Ops Fabric API

Read-only runtime slice for Prophet Real-Time Ops Fabric.

This service turns operational samples into report-only proposal records. It owns no deployment writer and no direct platform state writer in this slice.

## Routes

- `GET /healthz`
- `GET /readyz`
- `POST /v1/ops/events`
- `GET /v1/ops/events`
- `POST /v1/ops/proposals/rightsize`
- `GET /v1/ops/proposals`
- `GET /v1/ops/proposals/{proposal_id}`
- `GET /v1/ops/search-records`

## Search records

`/v1/ops/search-records` emits `OPS_FABRIC` records for Sherlock Search and Lampstand-style indexing. Records currently cover telemetry events and action proposals.

## Integration seams

- `global-devsecops-intelligence` supplies operations-domain intelligence references.
- `sherlock-search` retrieves proposal and evidence records through the platform search lane.
- `policy-fabric` evaluates proposal legality in a later slice.
- `agentplane` receives reviewed handoff candidates in a later slice.

v0.1 remains report-only.
