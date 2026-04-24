# Ops Fabric Schemas

This directory contains v0.1 contracts for Prophet Real-Time Ops Fabric.

The contracts are deliberately small and report-only:

- `evidence-ref.schema.v0.1.json` references supporting operational evidence.
- `intelligence-ref.schema.v0.1.json` references operations-domain intelligence from `global-devsecops-intelligence`.
- `telemetry-event.schema.v0.1.json` captures normalized operational facts.
- `action-proposal.schema.v0.1.json` represents a resource-governor recommendation.
- `handoff-candidate.schema.v0.1.json` represents a report-only AgentPlane or GitOps handoff candidate.

v0.1 does not permit autonomous mutation.
