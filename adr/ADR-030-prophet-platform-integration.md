# ADR-030: Prophet Platform as the integration target for platform/infrastructure management

## Status
Proposed

## Context
We have an older platform/infrastructure scaffold that includes:
- application services (`apps/`)
- deployment wiring (Argo CD + Kustomize)
- protocol/docs stubs (triRPC notes, examples)
- portal UI wiring

We need a canonical place to integrate these patterns without polluting standards repos.

## Decision
We adopt `SocioProphet/prophet-platform` as the integration target for:
- platform runtime services (API, gateway, portal)
- infrastructure deployment wiring (GitOps)
- platform-level documentation

Standards remain in dedicated standards repositories and are consumed here via pinned commits/releases.

## Consequences
- This repo becomes the operational integration point (ship + run).
- We must keep standards artifacts versioned and referenced, not forked.
- Infrastructure and app code share one repo but are separated by clear directory boundaries.
