# ADR-031: Runtime transport topology for `prophet-platform`

## Status

Accepted

## Context

The repo currently documents UDS as the default internal wire shape, but the Kubernetes seed deploys API and gateway as separate workloads.
That makes a shared UDS path impossible unless the containers are explicitly colocated in one pod and share the same filesystem path.

## Decision

The platform uses a dual-mode topology:

- **local / same-host bootstrap**: `unix://...`
- **independently scheduled Kubernetes bootstrap**: `tcp://...`

This ADR separates **address family** from **protocol maturity**.
The current bootstrap code remains plaintext health traffic.
The next transport patch will keep the same address model and swap in the pinned TritRPC v1 implementation.

## Consequences

- the platform stops pretending UDS works across unrelated pods
- local development remains simple and inspectable
- the existing API/gateway split can continue in Kubernetes without broken socket assumptions
- a later TritRPC v1 integration no longer needs to redesign manifests and runtime config at the same time
