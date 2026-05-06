# Personal Intelligence Cell ClickHouse Facts

Status: first analytical-plane hardening lane
Related service: `apps/cell-service/`
Related issue: `#384`

## Purpose

The Personal Intelligence Cell runtime now emits analytical facts alongside control-plane state. Postgres owns durable control-plane objects; ClickHouse owns hot scoring, feedback, notification, and watch-pattern metrics.

## Implemented fact tables

The first service emission lane covers four of the seven planned analytical tables:

```text
cell_signal_scores
cell_feedback_outcomes
cell_notification_metrics
cell_watch_pattern_metrics
```

These are backed by the schema in:

```text
infra/datastores/clickhouse/cell/0001_personal_intelligence_cell_analytics.sql
```

## Fact emitters

Implemented in:

```text
apps/cell-service/src/cell_service/clickhouse_facts.py
```

The module provides:

- `CellFactSink` protocol;
- `InMemoryCellFactSink` for tests, smoke, and local demos;
- `ClickHouseCellFactSink` for live inserts through a small connection protocol;
- `signal_score_fact`;
- `feedback_outcome_fact`;
- `notification_metric_fact`;
- `watch_pattern_metric_fact`.

## Service integration

`CellService` emits facts automatically:

- `ingest_signal(...)` emits `cell_signal_scores` and `cell_watch_pattern_metrics`;
- `emit_feed_item(...)` emits `cell_notification_metrics`;
- `record_feedback_event(...)` emits `cell_feedback_outcomes`;
- `run_loop_contract(...)` includes an `analytics` snapshot when using the in-memory fact sink.

## First fact lineage

```text
Signal -> cell_signal_scores
Signal -> cell_watch_pattern_metrics
FeedItem -> cell_notification_metrics
FeedbackEvent + Signal -> cell_feedback_outcomes
```

## Not yet implemented

The following planned analytical tables exist in the ClickHouse schema but are not emitted by the service yet:

```text
cell_source_quality_facts
cell_reputation_deltas
cell_social_environment_snapshots
```

These belong to the next hardening lanes:

- source quality learning from feedback aggregates;
- reputation anti-manipulation primitives;
- SocioSphere social environment snapshots.

## Validation

Offline validation:

```bash
python3 tools/validate_cell_clickhouse_facts.py
python3 tools/validate_personal_intelligence_cell.py
python3 tools/smoke_cell_service_loop.py
```

The tests use `InMemoryCellFactSink` and a fake ClickHouse connection. Live ClickHouse integration is intentionally deferred until deployment configuration is ready.
