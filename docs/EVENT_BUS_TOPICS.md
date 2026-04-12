# Event Bus Topics

This document defines the initial zone-first topic plan for `prophet-platform`.

## Initial topic families

### Edge ingress
- `zone.edge.ingest.carrier_ingested.v1`
- `zone.edge.receipt.created.v1`
- `zone.edge.catalog.appended.v1`
- `zone.edge.membrane.admitted.v1`
- `zone.edge.membrane.quarantined.v1`

### Workspace promotion
- `zone.workspace.asset.promote_requested.v1`
- `zone.workspace.asset.promoted.v1`
- `zone.workspace.schema_link.candidate_created.v1`
- `zone.workspace.schema_link.promoted.v1`

### Platform orchestration
- `zone.platform.workflow.approval_requested.v1`
- `zone.platform.workflow.approval_decided.v1`
- `zone.platform.outbox.dispatch_requested.v1`
- `zone.platform.outbox.dispatch_completed.v1`

## Key rule

Topics should carry imported envelope semantics and preserve evidence/receipt lineage across crossings.
