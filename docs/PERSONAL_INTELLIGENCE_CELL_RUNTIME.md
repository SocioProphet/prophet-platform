# Personal Intelligence Cell Runtime

Status: draft implementation design
Normative source: `SocioProphet/socioprophet-agent-standards/docs/PERSONAL_INTELLIGENCE_CELL.md`
Schema source: `SocioProphet/socioprophet-agent-standards/schemas/personal-intelligence-cell.schema.json`
Tracking issue: `#384`

## Purpose

This document binds the Personal Intelligence Cell standard into `prophet-platform` runtime work. The goal is to turn Aigents-derived lessons into governed SocioProphet infrastructure without adopting Aigents as a runtime dependency.

The runtime lane proves this loop:

```text
create cell -> configure cell -> add source -> add typed watch pattern -> ingest source item -> extract typed variables -> create signal -> score novelty/relevance/confidence/trust -> policy check -> emit feed item -> append intent event -> receive feedback event -> update watch/source/reputation state -> export archive -> publish private/RSS feed -> publish slash-topic/New-Hope/Sherlock surfaces
```

## Runtime placement

`prophet-platform` owns deployable services, contracts, datastores, platform docs, validation, smoke tests, and runtime bindings. The Personal Intelligence Cell runtime belongs here as a platform service, not as a standalone experiment.

## Proposed service

Add:

```text
apps/cell-service/
contracts/cell/
schemas/cell/
infra/datastores/postgres/migrations/cell/
infra/datastores/clickhouse/cell/
docs/PERSONAL_INTELLIGENCE_CELL_RUNTIME.md
```

## Runtime resources

The first service pass must support these resources:

- `Cell`
- `CellConfig`
- `Watch`
- `WatchPattern`
- `Source`
- `Signal`
- `Peer`
- `ReputationEvent`
- `IntentEvent`
- `FeedbackEvent`
- `FeedItem`
- `ChannelAdapter`
- `CellArchive`
- `PrivateFeedDocument`
- `RssFeedDocument`
- `SlashTopicSurface`
- `NewHopeMembraneEvent`
- `SherlockSearchPacket`

## API surface

The first transport binding should follow existing platform conventions and remain compatible with TriTRPC internal service traffic.

Minimum logical routes:

```text
cell.health.v1/Health.Ping
cell.registry.v1/Cell.Create
cell.registry.v1/Cell.Get
cell.registry.v1/Cell.List
cell.config.v1/CellConfig.Put
cell.config.v1/CellConfig.Get
cell.watch.v1/Watch.Create
cell.watch.v1/Watch.Get
cell.watch.v1/Watch.List
cell.watch.v1/WatchPattern.Create
cell.watch.v1/WatchPattern.Validate
cell.source.v1/Source.Create
cell.source.v1/Source.Get
cell.source.v1/Source.List
cell.signal.v1/Signal.Ingest
cell.signal.v1/Signal.Score
cell.signal.v1/Signal.Get
cell.feed.v1/FeedItem.Emit
cell.feed.v1/FeedItem.List
cell.feed.v1/PrivateFeed.Export
cell.feed.v1/RssFeed.Export
cell.publication.v1/PublicationBundle.Build
cell.publication.v1/SlashTopicSurface.Build
cell.publication.v1/NewHopeMembraneEvent.Build
cell.publication.v1/SherlockSearchPacket.Build
cell.feedback.v1/FeedbackEvent.Record
cell.intent.v1/IntentEvent.Append
cell.intent.v1/IntentEvent.ReplayDryRun
cell.archive.v1/CellArchive.Export
cell.archive.v1/CellArchive.RestoreDryRun
```

Browser and external API access should go through the platform gateway. Direct service access should stay internal.

## Storage model

### Postgres control plane

Tables:

```text
cells
cell_configs
watches
watch_patterns
sources
signals
peers
reputation_events
intent_events
feedback_events
feed_items
channel_adapters
cell_archives
```

Postgres owns durable control-plane state, lifecycle state, policy references, archive manifests, and replayable intent logs.

### ClickHouse analytical plane

Tables:

```text
cell_signal_scores
cell_source_quality_facts
cell_reputation_deltas
cell_feedback_outcomes
cell_watch_pattern_metrics
cell_notification_metrics
cell_social_environment_snapshots
```

ClickHouse owns hot analytical facts, temporal profiles, relevance performance, source quality, and relationship/source hygiene metrics.

### Evidence/provenance objects

The first pass may store evidence as references only. Lampstand integration should later attach retrieval artifacts, excerpts, hashes, document refs, crawl metadata, and source provenance.

## Policy gate

Every operation must produce or cite a policy decision when it can observe, remember, share, publish, notify, or act.

Required gates:

```text
observe_source
remember_signal
share_signal
publish_feed_item
publish_slash_topic_surface
publish_new_hope_membrane_event
publish_sherlock_search_packet
notify_actor
delegate_to_peer
use_channel_adapter
export_cell_archive
restore_cell_archive
```

The first implementation may use a stub allow/deny policy engine, but the contract must make the policy boundary explicit.

## StructuredIntent requirement

Every user, UI, CLI, channel, and agent-triggered action must append an `IntentEvent` with:

- readable `intent_text`;
- machine-readable `structured_intent`;
- policy decision;
- tool calls or service calls;
- emitted events;
- reversibility marker.

This gives us replay, audit, debugging, governance, and cross-surface parity.

## WatchPattern validation

`WatchPattern.Validate` must support deterministic validation before any LLM or embedding expansion.

First validation checks:

- variable names are valid;
- typed variables have valid types;
- frames reference known variables;
- examples compile;
- validation fixtures produce expected extraction keys;
- policy triggers cite policy references;
- graph patterns declare entity and edge expectations.

## Scoring

`Signal.Score` must return at least:

- novelty score;
- relevance score;
- confidence score;
- source trust score;
- optional reputation effects;
- explanation fields sufficient for audit.

Initial scoring can be heuristic:

- novelty: hash/content similarity against recent cell signals;
- relevance: pattern match confidence + source scope match;
- confidence: extraction quality + evidence quality;
- source trust: source profile default or learned trust;
- reputation effects: empty or stubbed until reputation lane lands.

## Feed and publication bridges

`FeedItem` is not the final surface. A governed cell feed item must be exportable into all first-class discovery and commons surfaces:

1. `PrivateFeedDocument`
   - canonical JSON feed for the owning cell;
   - includes policy decision, signal summary, evidence refs, scores, and extractions.

2. `RssFeedDocument`
   - RSS 2.0-compatible XML derived from the private feed;
   - intended for user-controlled subscriptions and low-friction interoperability.

3. `SlashTopicSurface`
   - topic-scoped publication record;
   - maps cell/watch/signal/feed lineage into a governed `/cell/...` topic ref;
   - preserves policy decision refs and evidence refs.

4. `NewHopeMembraneEvent`
   - carrier/receptor/membrane event for commons/news/messaging semantics;
   - maps policy decision to membrane outcome: allow -> admit, deny -> reject, quarantine -> quarantine, review/redact -> hold;
   - preserves claim/citation/entity and lineage fields.

5. `SherlockSearchPacket`
   - search packet compatible with Sherlock's search/discovery lane;
   - maps the signal to a workroom-scoped result with confidence, freshness, citation refs, evidence refs, and policy decision refs.

This keeps Personal Intelligence Cell output aligned with slash-topics, New Hope membranes, and Sherlock Search from the first feed/export milestone.

## Feedback loop

`FeedbackEvent.Record` must support:

- follow;
- mark relevant;
- mark irrelevant;
- delete;
- mute source;
- promote source;
- refine watch;
- share;
- save;
- dismiss.

The first learning pass should update source quality, watch-pattern metrics, and notification suppression data.

## Archive/export

`CellArchive.Export` must produce a manifest containing:

- cell metadata;
- config inventory;
- watch inventory;
- source inventory;
- peer inventory;
- signal inventory or redacted signal inventory;
- feed inventory;
- intent-event inventory;
- schema version;
- redaction policy;
- migration target compatibility.

`CellArchive.RestoreDryRun` must validate schema version, policy compatibility, missing dependencies, and redaction status before any restore.

## Channel adapters

Every channel adapter must include:

- direction;
- auth profile reference;
- policy reference;
- rate limits;
- delivery guarantee;
- cleanup policy;
- failure policy;
- enabled flag.

No channel adapter may bypass IntentEvent logging.

## Conformance fixtures

Add test fixtures for:

- weather alert;
- real estate listing;
- market offer;
- competitor release;
- legal/public hearing;
- political/public event;
- GitHub/repository change;
- regulatory/standards change.

Each fixture should prove:

- source ingestion;
- pattern extraction;
- signal creation;
- evidence/provenance reference;
- score generation;
- policy gate;
- feed item;
- private/RSS feed export;
- slash-topic surface;
- New Hope membrane event;
- Sherlock search packet;
- feedback event.

## Implementation milestones

### Milestone 1: contracts and validation

- copy or vendor pinned schema from standards into `schemas/cell/`;
- add validation helper;
- add fixture examples;
- wire `make validate`.

### Milestone 2: service skeleton

- add `apps/cell-service/`;
- implement health;
- implement in-memory create/get/list for Cell, CellConfig, Source, Watch, WatchPattern;
- add smoke test.

### Milestone 3: signal loop

- implement Signal.Ingest;
- implement deterministic WatchPattern validation;
- implement heuristic Signal.Score;
- emit FeedItem;
- append IntentEvent.

### Milestone 4: persistence

- add Postgres migrations;
- persist control-plane resources;
- add ClickHouse fact stubs for scoring and feedback outcomes.

### Milestone 5: policy and archive

- add explicit policy stub;
- add CellArchive.Export;
- add CellArchive.RestoreDryRun;
- make smoke test cover export.

### Milestone 6: feed and publication bridges

- export private JSON feed;
- export RSS 2.0-compatible feed;
- build slash-topic surface;
- build New Hope membrane event;
- build Sherlock search packet.

### Milestone 7: Lampstand adapter

- integrate Lampstand as first bounded Source adapter;
- preserve evidence and provenance artifacts;
- add source/watch/signal fixture around local indexed content.

## Non-goals

- no Aigents Java runtime dependency;
- no Aigents Language protocol dependency;
- no telnet-style administration;
- no generic crawler before the loop is proven;
- no ungoverned sharing;
- no blockchain/payment adapter enabled by default;
- no reputation score without provenance and context.
