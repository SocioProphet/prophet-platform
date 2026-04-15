# Live Telemetry Inspector v0.1

## Purpose

Define the first user-visible transparency surface for the transparent telemetry system.
The inspector is not an operator-only debug console. It is a product surface that lets users and internal reviewers see what telemetry fired, why it fired, what policy did to it, where it went, how long it lasts, and whether it was optional.

## Core requirements

1. Show recent events in near real time.
2. Show policy outcomes, not just raw emitter intent.
3. Distinguish mandatory from optional telemetry.
4. Show transformed outbound fields, not hidden pre-transform fields.
5. Show destinations and retention deadlines.
6. Show receipts for expiry and deletion.
7. Support export of visible ledger rows.
8. Avoid exposing raw content in the inspector.

## Primary views

### Activity stream
A chronological table of telemetry decisions.

Columns:
- time
- event
- plane
- status
- mandatory or optional
- destination summary
- retention
- receipt id

### Event detail drawer
When a row is opened, show:
- event name
- manifest version
- purpose
- trigger
- plane
- policy version
- user control state snapshot
- action taken
- transformed fields actually sent
- blocked reason or transform reason
- destination sinks
- retention deadline
- integrity hash
- related receipt ids
- whether user can disable this event family

### Controls panel
Show active control states by plane:
- service integrity telemetry
- product analytics
- experimentation
- developer diagnostics

Mandatory planes should be visibly locked with explanation.

### Export panel
Allow export of the current filtered ledger range as JSONL first, with CSV summary optional later.

## UI state definitions

### Allowed
Event passed policy and was routed to at least one sink.

### Blocked
Event was prevented from being sent. Show blocked reason and whether the block came from user settings, policy, invalid schema, or jurisdiction rule.

### Transformed
Event was sent after coarsening or redaction. Show which fields were transformed and note that raw values were not sent.

### Aggregated
Multiple local emissions collapsed into one bounded summary event. Show aggregation window and aggregation scope.

### Sampled
Event family is sampled and this event was kept or dropped. Show sampling policy.

### Delayed
Event is buffered until a later flush or safer boundary. Show delay reason.

### Expired
Retention window elapsed and the stored object was removed by policy.

### Deleted
Explicit deletion occurred due to user request or policy.

## Filters

Users should be able to filter by:
- plane
- status
- mandatory vs optional
- destination
- time range
- event family
- current session vs recent sessions

## Privacy constraints

1. Do not show raw prompt text.
2. Do not show raw assistant text.
3. Do not show raw file names in the reference slice.
4. Do not show raw citation URLs unless explicitly permitted by a future manifest and view.
5. Show transformed outbound fields only.
6. Hide operator-only fields from the user view.

## Reference slice expected rows

For a clean streamed turn with citations:
1. reliability.conversation.stream.started -> Allowed
2. analytics.turn.rendered.summary -> Aggregated then Allowed, or Blocked if analytics disabled
3. analytics.citations.rendered.summary -> Aggregated then Allowed, or Blocked if analytics disabled
4. receipts.citation_resolution.summary -> Allowed
5. reliability.conversation.stream.completed -> Allowed

For a degraded turn with missing final message:
1. reliability.conversation.timeout_reached -> Allowed
2. reliability.conversation.stream.incomplete -> Allowed
3. reliability.conversation.resume.attempted -> Allowed
4. reliability.conversation.resume.succeeded or failed -> Allowed

## Bottom line

The inspector is the product proof that telemetry is transparent. Without this surface, the rest of the architecture remains internally disciplined but externally opaque.