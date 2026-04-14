# cloudshell-fog Fog Stack Access Binding v0

This document binds the `cloudshell-fog` platform deployment work in `prophet-platform` to the broader **Fog Stack Access** offering model.

## 0. Purpose

`cloudshell-fog` is not just a standalone shell capability. It is the primary source capability for the Fog Stack Access offering and is deployed on the Prophet Platform substrate.

This document explains how the platform-side assets in this repo map to that offering model.

## 1. Canonical split

### Capability source
- `SocioProphet/cloudshell-fog`

Owns:
- shell-specific HTTP/WSS API
- placement engine
- policy engine
- runtime connector interface
- capability-local docs and deployment guidance

### Substrate
- `SocioProphet/prophet-platform`

Owns:
- deployable platform services and runtime wiring
- platform contracts and evidence surfaces
- K8s / Argo / validation assets
- standard and federal deployment lanes

### Standards / governance input
- `SocioProphet/prophet-platform-standards`

Owns reusable governance and platform baseline material.

## 2. Runtime-class mapping

Fog Stack Access spans multiple runtime classes and must not be flattened into one orchestrator story.

### Edge service
Browser-facing gateway and attach path.

Current platform landing points:
- gateway-facing runtime deployment assets
- Argo applications for standard and federal runtime lanes

### Cluster service
Session lifecycle, allocation, policy mediation, and runtime coordination.

Current platform landing points:
- contracts for session / placement / policy events
- runtime overlays and profile config
- policy application lane

### Local / field runtime
Still possible through local-eval and stub connectors, but not represented here as a production platform lane.

## 3. Offering-level evidence expectations

Fog Stack Access requires more than raw deployment.

Representative required evidence classes include:
- bundle manifest
- component-version manifest
- SBOM
- provenance attestation
- compatibility statement

This repo now carries the substrate-side beginnings of that evidence model for `cloudshell-fog`.

## 4. Current prophet-platform artifacts that satisfy the binding

- runtime-v2 guide
- policy Argo lane
- standard and federal stack entrypoints
- deployment inventory contract
- production decision-record contract
- session event contract
- readiness and go-live validators

## 5. Remaining work

To make the Fog Stack Access binding stronger, this repo should keep extending:

- component-version manifest
- compatibility statement
- support window / release-channel references
- conformance validators tied to the offering profile

## 6. Result

Within `prophet-platform`, `cloudshell-fog` is the runtime/deployment substrate realization of the Fog Stack Access offering, not a parallel product definition.
