# Regis / ACR Service Integration for Prophet Platform

Version: v0.1
Status: draft integration plan
Owner: Prophet Platform runtime and deployment hub

## Purpose

This document defines how Regis Entity Graph / Authority Concordance Rex (ACR) becomes a deployable service over Prophet Platform.

Prophet Platform is the runtime and deployment hub for SocioProphet. Standards and governance remain in dedicated upstream repositories; this repository is where those standards become running services, concrete deployment topologies, and platform contracts.

## Platform fit

The current platform topology already provides the right service lane:

- `apps/` contains deployable services.
- `contracts/` contains platform-facing event, evidence, and receipt contracts consumed by runtime services.
- `infra/` contains deployment wiring such as Kustomize, Argo CD appsets, namespaces, and local deployment assets.
- `tools/` contains validation and smoke-test helpers.
- Runtime services use TriTRPC v1 for internal traffic, with HTTP gateway exposure for browser or edge access where needed.

Therefore Regis / ACR should land as a platform service, not only as a repository-local schema pack.

## Service target

Service name: `regis-acr-api`

Initial responsibility:

- accept source records
- emit evidence claims
- propose concordance links
- write decision-ledger entries
- emit energy-ledger entries for resolver runs
- expose promotion-policy evaluation
- expose relationship-formation hooks for Ontogenesis

Non-goal for first tranche:

- no irreversible canonical merge automation
- no cross-prime identity collapse
- no cloud override of citizen-local state
- no unreviewable high-stakes decisioning

## Runtime placement

Recommended initial placement:

- app: `apps/regis-acr-api/`
- contracts: `contracts/acr/`
- schemas: `schemas/acr/`
- local smoke output: `build/regis-acr/`
- infra base: `infra/k8s/regis-acr-api/`
- validation tool: `tools/validate_regis_acr_integration.py`
- smoke tool: `tools/smoke_regis_acr_service.py`

## Contract imports

Normative domain source:

- `SocioProphet/regis-entity-graph`

Initial imported contract set:

- `CanonicalEntity`
- `SourceRecord`
- `ConcordanceLink`
- `EvidenceClaim`
- `DecisionLedgerEntry`
- `EnergyLedgerEntry`
- `PromotionPolicy`
- `RelationshipFormationHook`

Platform-facing runtime contracts should mirror the domain contracts while adding deployment/runtime metadata such as request id, receipt id, service version, route, and trace context.

## Service API surface

Initial routes or TriTRPC methods:

- `RegisAcr.IngestSourceRecord.REQ` -> `RegisAcr.IngestSourceRecord.RES`
- `RegisAcr.ProposeConcordance.REQ` -> `RegisAcr.ProposeConcordance.RES`
- `RegisAcr.EvaluatePromotion.REQ` -> `RegisAcr.EvaluatePromotion.RES`
- `RegisAcr.EmitDecisionLedger.REQ` -> `RegisAcr.EmitDecisionLedger.RES`
- `RegisAcr.EmitRelationshipFormationHook.REQ` -> `RegisAcr.EmitRelationshipFormationHook.RES`
- `RegisAcr.Health.Ping.REQ` -> `RegisAcr.Health.Ping.RES`

HTTP gateway routes may later mirror these as:

- `GET /regis-acr/health`
- `POST /regis-acr/source-records`
- `POST /regis-acr/concordance/proposals`
- `POST /regis-acr/promotion/evaluate`
- `POST /regis-acr/decisions`
- `POST /regis-acr/relationships/formation-hooks`

## Minimal deployment topology

For the first service tranche:

- stateless API process
- local JSON fixture store or Postgres-backed store depending on environment
- no automatic canonical promotion without policy decision
- evidence and decision receipts emitted for every consequential action
- health route wired into platform smoke tests

## Integration with existing platform lanes

### Evidence receipts

Regis / ACR should emit evidence receipts for source-record ingestion, concordance proposals, promotion evaluations, decision-ledger writes, and relationship-formation hooks.

### Policy Fabric

Promotion decisions should be delegated to or checked against Policy Fabric once policy-pack integration is available.

### Ontogenesis

Relationship formation hooks and canonical entity formation records should bind to Ontogenesis lifecycle semantics.

### Lattice Studio / platform records

The existing platform already emits platform records from service and catalog surfaces. Regis / ACR should register itself as a platform service record so it can participate in catalog, deployment, and local-dev surfaces.

### TriTRPC

Internal traffic should follow the platform TriTRPC binding. HTTP exposure should be gateway-mediated.

## Validation targets

Initial validation should check:

- contract pack presence
- schema presence
- example fixture presence
- service health response
- source-record ingest fixture
- concordance proposal fixture
- promotion evaluation fixture
- decision-ledger fixture
- Ontogenesis relationship hook fixture

## Initial implementation queue

1. Copy or mirror ACR contract pack metadata into `contracts/acr/`.
2. Add a minimal `apps/regis-acr-api/` service with health and fixture-backed ingest/proposal endpoints.
3. Add `tools/validate_regis_acr_integration.py` to verify contract and fixture presence.
4. Add `tools/smoke_regis_acr_service.py` to exercise service behavior locally.
5. Add Makefile targets for validation and smoke testing.
6. Add Kustomize deployment base under `infra/k8s/regis-acr-api/`.

## Acceptance criteria

- `make validate-regis-acr-integration` passes.
- `make smoke-regis-acr-service` passes.
- The service emits a health response.
- The service accepts a source-record fixture and emits an evidence/decision response.
- Promotion evaluation is policy-gated and does not auto-promote low-margin matches.
- Ontogenesis relationship hook fixture is emitted but not forced into canonical state.
