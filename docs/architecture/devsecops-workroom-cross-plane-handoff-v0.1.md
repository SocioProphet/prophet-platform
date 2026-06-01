# DevSecOps Workroom Cross-Plane Handoff v0.1

Status: cross-plane handoff contract note  
Plane: Prophet Platform orchestration over Sociosphere and AgentPlane  
Parent: `docs/architecture/devsecops-intelligence-workroom-v0.1.md`

## Purpose

This note defines the first Workroom handoff boundary across Sociosphere, AgentPlane, and Prophet Platform.

The Workroom must consume environment, runtime, receipt, and topology references without taking ownership of their truth.

## Plane ownership

### Sociosphere

Sociosphere owns:

- workspace state;
- environment profile state;
- environment request/readout state;
- runtime evidence ingestion state;
- state transitions from `environment_observed` to runtime-aware states such as `runtime_allocated` and `runtime_failed`.

Relevant validator:

```text
SocioProphet/sociosphere: tools/validate_runtime_evidence_ingestion.py
```

This validates Sociosphere ingestion fixtures for AgentPlane runtime evidence refs.

### AgentPlane

AgentPlane owns:

- sandbox runtime run records;
- execution evidence refs;
- receipt refs;
- dependency graph refs;
- routing refs;
- network/async/stateful isolation refs;
- teardown and leak-check state.

Relevant schema:

```text
SocioProphet/agentplane: schemas/sandbox/runtime-sandbox-run.v0.1.schema.json
```

### Prophet Platform

Prophet Platform owns:

- product/API invocation surface;
- Workroom projection;
- Workroom record validation;
- report/bundle generation;
- claim boundary enforcement at the product layer.

Relevant validators:

```text
tools/validate_devsecops_workroom.py
tools/validate_devsecops_validation_run_receipt_ref.py
tools/smoke_generate_workroom_from_validate_change_v2.py
tools/build_validate_change_workroom_bundle.py
```

## Current handoff evidence

### AgentPlane allocated runtime fixture

AgentPlane allocated runtime fixture provides:

- `runtimeRunId`;
- `requestRef`;
- `runtimeParityLevel`;
- `runStatus`;
- `environmentRef`;
- `baselineRef`;
- `dependencyGraphRef`;
- `routingRef`;
- `isolationRefs`;
- `evidenceRefs`;
- `receiptRefs`;
- `teardownState`;
- `leakCheckRef`.

### Sociosphere runtime evidence ingestion fixture

Sociosphere allocated ingestion fixture consumes equivalent refs under snake_case names:

- `agentplane_refs.runtime_run_ref`;
- `agentplane_refs.environment_ref`;
- `agentplane_refs.dependency_graph_ref`;
- `agentplane_refs.routing_ref`;
- `agentplane_refs.isolation_refs`;
- `agentplane_refs.evidence_refs`;
- `agentplane_refs.receipt_refs`;
- `agentplane_refs.leak_check_ref`.

The fixture records runtime evidence state while preserving blocking gaps such as teardown and leak-check incompleteness.

### Prophet Workroom consumption

Prophet Platform consumes Workroom-compatible refs through:

- `validate_change` v2 response fixtures;
- Workroom adapter-generated records;
- validation run receipt refs;
- Workroom bundle output.

Prophet does not issue, sign, or verify Sociosphere/AgentPlane receipts.

## Required cross-plane invariant

The following refs must remain consistent across the planes:

| Concept | AgentPlane | Sociosphere | Prophet Workroom |
| --- | --- | --- | --- |
| Runtime run | `runtimeRunId` | `agentplane_refs.runtime_run_ref` | `source_refs.validation_run_ref` |
| Environment | `environmentRef` | `agentplane_refs.environment_ref` | `behavioral_divergence_event.environment_ref` or source-derived env ref |
| Dependency graph | `dependencyGraphRef` | `agentplane_refs.dependency_graph_ref` | topology/dependency evidence ref |
| Routing | `routingRef` | `agentplane_refs.routing_ref` | routing/topology evidence ref |
| Isolation | `isolationRefs` | `agentplane_refs.isolation_refs` | topology/runtime evidence context |
| Evidence | `evidenceRefs` | `agentplane_refs.evidence_refs` | `evidence_packets[].evidence_ref` |
| Receipt | `receiptRefs` | `agentplane_refs.receipt_refs` | `source_refs.validation_receipt_ref` / receipt evidence provenance |
| Leak check | `leakCheckRef` | `agentplane_refs.leak_check_ref` | parity blocking gap context |

## Runtime parity boundary

`runtime_observed` in a Workroom record means that receipt-backed runtime evidence was represented and validated for the scoped record.

It does not mean full Signadot-style feature parity.

Full Signadot-style feature parity still requires observed evidence for:

- PR-scoped lifecycle;
- changed-service-only deploy;
- baseline fallback;
- HTTP/gRPC route isolation;
- async queue/topic isolation;
- stateful resource isolation;
- validation job execution;
- teardown and TTL completion;
- policy, secret, and data-boundary enforcement;
- agent-facing control surface.

## Next implementation requirement

The next Workstream 4 implementation should add a direct cross-plane fixture check that starts from an AgentPlane runtime sandbox run fixture, maps it into a Sociosphere runtime evidence ingestion fixture, and then maps it into a Prophet Workroom projection.

The check should prove reference identity preservation across all three planes without executing infrastructure.

## Non-claims

This handoff note does not execute sandbox infrastructure.

This handoff note does not allocate runtime environments.

This handoff note does not certify Signadot feature parity.

This handoff note does not grant production mutation authority.
