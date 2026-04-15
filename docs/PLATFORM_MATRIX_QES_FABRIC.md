# Platform Matrix/QES Fabric

This document defines the **platform-owned Matrix/QES lane** for Prophet Platform.

The purpose of the lane is to give SocioProphet one coherent place to:
- run operator-facing incident and evaluation workflows through Matrix
- preserve replayable control-plane and operator evidence
- separate runtime telemetry from policy, orchestration, and human approval
- bind event transport, control resolution, and operator actions into one platform contract family
- prepare a clean path from local scaffolds to Kafka/Redpanda, Matrix homeserver, PostgreSQL, ClickHouse, and Temporal-backed execution

## Why this belongs in `prophet-platform`

This repository is the runtime and deployment hub for the platform. Matrix/QES is not a detached chatbot or a generic notification bot. It is part of platform responsibility because it owns:
- operator action contracts
- evaluation and replay orchestration entrypoints
- Matrix room/thread lifecycle handling
- control-plane resolution snapshots
- runtime gateway registration and flush semantics
- local and cluster deployment wiring for the lane

Dedicated standards and ADRs remain upstream in `prophet-platform-standards`. This repository carries the **executable platform landing** that consumes those standards.

## Standards alignment

This lane should align to the following standards families and platform conventions:
- **AsyncAPI** for event-channel and message-contract description
- **CloudEvents-style event envelopes** for explicit event metadata and traceability
- **OpenFeature-compatible control resolution** for flags, configs, and layers
- **OpenTelemetry** for trace and runtime observability
- **Matrix Client-Server API** semantics for room, thread, and operator command surfaces
- repo-wide evidence and receipt posture already used elsewhere in `prophet-platform`

## Responsibility boundaries

### Platform responsibility

The platform lane is responsible for:
- Matrix operator thread lifecycle
- control resolution snapshotting
- replay-request contract emission
- gateway registration, track, profile, and flush family semantics
- queueing and backpressure policy at the platform edge
- runtime evidence and audit surfaces

### Product / domain responsibility

Model-specific or domain-specific repos remain responsible for:
- domain content packs
- product-specific UX behavior
- model internals
- domain-specific evaluation logic and prompt assets

### Shared responsibility

Shared objects across platform and product lanes include:
- replay artifacts and references
- policy lineage
- context slices and workspace identity
- operator approval metadata
- evidence and receipt references

## Plane split

### Data plane
- normalized events
- operator action events
- replay requests/results
- quality observations
- gateway registration and flush events

### Control plane
- flags
- dynamic configs
- layers
- policy snapshots
- symbolic registry to wire mapping

### Operator plane
- Matrix room/thread lifecycle
- command parsing
- replay approval / rejection
- suppress / unsuppress / resolve / reopen transitions

### Evaluation plane
- replay execution requests
- replay completion facts
- evidence preservation
- downstream scoring and observation emission

## Proposed repo landing points

- `apps/matrix-qes-operator/` — thin Matrix operator control surface
- `contracts/qes/events/` — canonical QES event families
- `docs/LOCAL_DEV_MATRIX_QES_FABRIC.md` — local operator runbook
- future `apps/matrix-qes-gateway/` — same-origin CES-style ingress facade once the operator lane is stable
- future `infra/local/docker-compose.matrix-qes.yml` — local runtime wiring for Matrix/QES services and datastores

## Event families for the first slice

- `matrix.operator.action.v1`
- `replay.requested.v1`
- `control.resolution.snapshot.v1`

These are the minimum contracts needed to keep Matrix operator actions, replay intent, and control-plane state auditably distinct.

## Security and responsibility posture

The Matrix/QES lane should follow the repo-wide platform posture:
- non-root runtime containers
- explicit environment variables only
- no secrets committed
- strict distinction between operator intent, policy evaluation, and execution outcome
- no accidental dependence on ambient document or UI runtime state

## Immediate implementation steps

1. Land a thin Matrix operator service with deterministic room/thread state transitions.
2. Land canonical event contracts for operator actions, replay requests, and control snapshots.
3. Keep the first slice local-state and API-thin so the repo gains a stable seam before Kafka/Matrix/Temporal bindings.
4. Add same-origin gateway, durable queues, and live homeserver wiring in subsequent slices.

## Next platform steps

1. Add a same-origin QES gateway facade compatible with the platform event and receipt posture.
2. Add OpenFeature-compatible provider resolution and snapshot emission inside the platform runtime.
3. Add staging Kafka/Redpanda, Matrix homeserver, PostgreSQL, ClickHouse, and Temporal integration tests.
4. Add dashboard and evidence-console integration for Matrix/QES surfaces.
