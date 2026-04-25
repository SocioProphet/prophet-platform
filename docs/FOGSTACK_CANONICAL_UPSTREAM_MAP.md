# FogStack Canonical Upstream Map

Purpose: record the current canonical upstream split so Fog runtime, policy, release-proof, and deployment work do not drift into parallel ownership across repositories.

## Canonical upstream homes

### 1. Shared Fog contract surface
Repository: `SocioProphet/api-spec`
Subtree: `fog/`

Owns:
- OpenAPI for Fog topology and planner APIs
- AsyncAPI for Fog telemetry and alerts buses
- shared JSON Schemas for Fog identity, posture, deployment profile, and claim objects
- CUE bundle seeds and upstream ADRs

Working rule:
- if a Prophet Platform runtime change needs a new shared Fog contract field or protocol surface, that change should land in `api-spec/fog/` in lockstep or first.

### 2. Shared Fog deployment and profile surface
Repository: `SocioProphet/manifests`
Subtree: `fog/`

Owns:
- base Fog kustomize packaging
- overlays for `single-home`, `multi-home`, and `regional-multimesh`
- shared site seed demos and deployment/profile notes

Working rule:
- if a Prophet Platform release/deployment change depends on a new shared Fog profile or overlay concept, that change should land in `manifests/fog/` in lockstep or first.

### 3. Fog runtime gateway surface
Repository: `SocioProphet/cloudshell-fog`

Owns:
- gateway runtime behavior
- connector selection and runtime connector implementations
- placement engine runtime behavior
- session lifecycle and PTY handling
- runtime-specific policy enforcement behavior
- operator runbooks and runtime deployment guidance

Working rule:
- runtime control-plane behavior belongs there, not in `prophet-platform`
- `prophet-platform` should consume or reference runtime outputs rather than redefine the gateway runtime itself

### 4. Fog release-proof and trust-graph surface
Repository: `SocioProphet/prophet-platform`

Owns:
- release seal execution
- release seal cryptographic verification record generation
- release proof pipeline wiring and CI
- trust/evidence graph mutation on the release-proof side

Working rule:
- release trust and proof artifacts belong here, but they should reference shared Fog contracts and deployment surfaces rather than becoming a second source of truth for them

### 5. Shared Fog policy contract surface
Repository: `SocioProphet/policy-fabric`

Owns:
- shared policy decision contracts that multiple runtimes may consume
- shared Fog posture/control request and decision schemas

Working rule:
- runtime-specific enforcement adapters can live in runtime repos, but shared Fog control decision shapes should land here

## Immediate implications for Prophet Platform

1. `prophet-platform` should continue to own Fog release-proof / trust-graph execution.
2. `prophet-platform` should not redefine shared Fog topology / planner / telemetry protocol authority locally.
3. `prophet-platform` should not become the canonical home for Fog deployment profiles or site overlays.
4. Runtime changes that belong to the gateway/session/connector/placement lane should go to `cloudshell-fog`.
5. Shared Fog control decision contracts should go to `policy-fabric`.

## Current upstream state

At the time of writing:
- the Fog shared contract subtree is already merged in `SocioProphet/api-spec`
- the Fog deployment/profile subtree is already merged in `SocioProphet/manifests`
- the runtime alignment and runtime fidelity lane is active in `SocioProphet/cloudshell-fog`
- the first shared Fog control-decision tranche is merged in `SocioProphet/policy-fabric`

This document exists so future Fog release-proof work in `prophet-platform` starts from that live upstream split rather than from a local or stale assumption.
