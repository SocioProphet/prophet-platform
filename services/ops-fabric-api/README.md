# Ops Fabric API

Read-only runtime slice for Prophet Real-Time Ops Fabric.

This service turns operational samples into report-only proposal records. It owns no deployment writer and no direct platform state writer in this slice.

## Initial routes

- `GET /healthz`
- `GET /readyz`
- `POST /v1/ops/proposals/rightsize`

## Integration seams

- `global-devsecops-intelligence` supplies operations-domain intelligence references.
- `sherlock-search` retrieves proposal and evidence records through the platform search lane.
- `policy-fabric` evaluates proposal legality in a later slice.
- `agentplane` receives reviewed handoff candidates in a later slice.

v0.1 remains report-only.
