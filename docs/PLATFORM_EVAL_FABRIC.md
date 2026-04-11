# Platform Evaluation, Observability, and Intelligence Fabric

This document defines the **platform-owned** evaluation and monitoring lane for Prophet Platform.

The purpose is to give SocioProphet one coherent place to:
- run offline evaluation suites
- monitor live platform behavior
- track profile scores and frontier tradeoffs
- ingest competitor and benchmark intelligence
- preserve replayable evidence for responsibility, governance, and audit

## Why this belongs in `prophet-platform`

This repo is the platform and infrastructure hub. The evaluation fabric is not just a model benchmark pack; it is part of platform responsibility.

It owns:
- metric and score schemas used by platform services
- local and cluster wiring for supporting datastores
- API surfaces for platform-level dashboards
- replay/provenance hooks for operational review
- profile-based ranking logic for internal decision support

It does **not** replace dedicated standards repos. Instead, it carries the executable platform wiring that consumes those standards.

## Proposed repo landing points

- `apps/eval-fabric-api/` — FastAPI starter surface for frontier, dossier, radar, and health routes
- `infra/local/docker-compose.eval-fabric.unified.yml` — unified local dev services for Postgres, ClickHouse, and the API
- `infra/datastores/postgres/` — transactional DDL for control-plane state
- `infra/datastores/clickhouse/` — analytical DDL for hot metric facts and ranking views
- `schemas/eval/` — canonical JSON schemas for metric definitions, metric facts, and context slices
- `docs/LOCAL_DEV_EVAL_FABRIC.md` — local operator runbook

## Responsibility boundaries

### Platform responsibility

The platform lane is responsible for:
- score provenance
- source trust classification
- freshness tracking
- reproducibility metadata
- confidence intervals and trial counts
- risk-tier and autonomy-tier slicing
- operational monitoring and alertability

### Product / model responsibility

Model-specific repos or providers remain responsible for:
- model internals
- model-specific prompt packs
- feature-level product behavior
- domain-specific eval content

### Shared responsibility

Some objects are shared across platform and product lanes:
- benchmark suite registration
- context-slice ontology
- replay artifact references
- policy and governance signals

## Datastore split

### Postgres

Use Postgres for transactional and control-plane state:
- metric definitions
- source descriptors
- context slices
- eval runs
- trials
- competitor snapshots

### ClickHouse

Use ClickHouse for analytical and time-series workloads:
- metric facts
- profile scores
- frontier slices
- momentum and radar aggregates

### Object storage / replay layer

Replay artifacts, prompt packs, methodology snapshots, and proof traces should live outside these databases and be referenced by durable IDs.

The current local platform path now emits local `EventEnvelope` / `EvidenceReceipt` artifacts for business-route reads when receipt emission is enabled.

## Canonical API surfaces

- `/healthz`
- `/readyz`
- `/v1/frontier`
- `/v1/models/{model_release_id}/dossier`
- `/v1/competition/radar`

## Security and responsibility posture

The evaluation fabric should follow the repo-wide platform posture:
- non-root containers
- minimal service footprint
- explicit env-var configuration
- no secrets committed
- strict distinction between reproduced internal measurements and external/public claims

## Next platform steps

1. Route emitted eval-fabric artifacts into broader platform event/evidence consumers and dashboard refresh flows.
2. Add judge metadata, reproducibility ledger entries, and causal attribution records.
3. Add dashboard and portal integration for frontier, dossier, and radar surfaces.
4. Add cluster overlays to the main platform inventory once the unified runtime and tests are stable.
