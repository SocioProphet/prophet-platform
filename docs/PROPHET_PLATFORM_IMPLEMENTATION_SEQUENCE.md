# Prophet Platform Implementation Sequence

## Purpose

This document turns the hosted service model into an execution order that fits the existing `prophet-platform` monorepo.

## Existing repo reality

`prophet-platform` already presents itself as a thin platform monorepo with:
- `apps/`
- `contracts/`
- `docs/`
- `infra/`
- `tools/`
- `libs/`

The implementation sequence below adapts the newer Sherlock/FogStack planning into that existing structure rather than replacing it.

## Phase A — freeze contracts and platform doctrine

Land and stabilize:
- `docs/PROPHET_PLATFORM_HOSTING_MODEL.md`
- `docs/FOGSTACK_SHERLOCK_PROPHET_INTEGRATION.md`
- `contracts/platform/service-catalog.yaml`
- `contracts/platform/deployment-profiles.yaml`
- `contracts/platform/hosting-boundaries.yaml`
- `contracts/platform/fogstack-normalized-objects.yaml`

Acceptance gate:
- service ownership, hosting boundaries, and deployment profile language are explicit and reviewable.

## Phase B — Wave 1 hosted runtime

Bring up and/or integrate:
- Identity Policy Service
- Search Evidence Service integration
- Case Triage Service integration
- Deep-Dive Orchestrator
- Dashboard BFF
- Matrix shell integration
- Dashboard shell

Recommended monorepo landing points:
- `apps/identity-policy/`
- `apps/deepdive-orchestrator/`
- `apps/dashboard-bff/`
- `apps/dashboard-shell/`
- `apps/matrix-shell-integration/`
- `apps/search-evidence-integration/`
- `apps/case-triage-integration/`

Acceptance gate:
- one hosted deployment can execute evidence-backed retrieval, case-linked triage, and deep-dive orchestration through the platform.

## Phase C — Wave 2 FogStack enrichment

Add:
- Topology Environment Service
- Artifact Release Service
- environment deep-dive mode
- artifact/release deep-dive mode
- operator-facing topology and artifact views

Recommended landing points:
- `apps/topology-environment/`
- `apps/artifact-release/`
- `apps/deepdive-viewer/`
- `apps/artifact-browser/`
- `apps/topology-explorer/`

Acceptance gate:
- platform can represent site/zone/room/node/radio/sensor/trust-domain topology and artifact/provenance/promotion state as live hosted surfaces.

## Phase D — Wave 3 adapters

Add:
- GitHub adapter
- Google Drive adapter
- Artifact Registry adapter
- KubeEdge adapter
- Cilium/Hubble adapter
- Tetragon adapter

Recommended landing points:
- `apps/github-adapter/`
- `apps/gdrive-adapter/`
- `apps/artifact-registry-adapter/`
- `apps/kubeedge-adapter/`
- `apps/cilium-hubble-adapter/`
- `apps/tetragon-adapter/`

Acceptance gate:
- environment and artifact evidence can be sourced from live systems through stable adapter contracts.

## Phase E — hardening and promotion

Add:
- replay fixtures for all platform-owned services
- profile/channel overlays in `infra/`
- rollback tests
- backup/restore drills
- provider tournament execution in hosted mode

Acceptance gate:
- deployment promotion is governed by digest, provenance, SBOM, signature state, replayability, and passing evaluation.

## Key rule

Do not treat `prophet-platform` as the sole source repo for everything.

It is the hosted runtime composition surface. Adjacent Sherlock repos should continue to own specialized logic where that boundary remains valuable.
