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

### Personal Intelligence Cell
- `zone.cell.signal.ingested.v1`
- `zone.cell.signal.scored.v1`
- `zone.cell.feed.item_emitted.v1`
- `zone.cell.feed.private_exported.v1`
- `zone.cell.feed.rss_exported.v1`
- `zone.cell.slash_topic.surface_built.v1`
- `zone.cell.new_hope.membrane_event_built.v1`
- `zone.cell.sherlock.search_packet_built.v1`
- `zone.cell.feedback.recorded.v1`
- `zone.cell.archive.exported.v1`

## Cell publication rule

Personal Intelligence Cell outputs must preserve the same signal/feed lineage across all publication surfaces:

```text
Cell -> Watch -> WatchPattern -> Signal -> FeedItem -> PrivateFeed/RSS -> SlashTopicSurface/NewHopeMembraneEvent/SherlockSearchPacket
```

The first publication lane is service-local and validation-backed. A later outbox lane should publish these records to the event bus only after the feed item policy decision allows publication.

## Key rule

Topics should carry imported envelope semantics and preserve evidence/receipt lineage across crossings.
