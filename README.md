# Prophet Platform (SocioProphet)

This repository is the **runtime and deployment hub** for the SocioProphet platform.

It is intentionally a **thin platform monorepo**:
- `apps/` contains deployable services (API, gateway, web portal, search/index daemons, execution services)
- `contracts/` contains platform-facing event, evidence, and receipt contracts consumed by runtime services
- `docs/` contains platform-level guidance (architecture, transport binding, security, roadmap)
- `infra/` contains deployment wiring (Kustomize, Argo CD appsets, namespaces, etc.)
- `tools/` contains validation and smoke-test helpers (`standards.lock.yaml` gates platform drift checks)
- `libs/` contains small shared runtime bindings that adapt pinned upstream standards into platform code

## Why this repo exists

Standards and governance stay in dedicated upstream repositories. `prophet-platform` is where those standards become running services, concrete deployment topologies, and platform contracts.

## Quickstart

```bash
make validate
make smoke-health
```

## Reading order

1. `docs/ARCHITECTURE.md`
2. `docs/TRITRPC_SPEC.md`
3. `docs/TRITRPC_PLATFORM_BINDING.md`
4. `contracts/`
5. `infra/k8s/`

## Notes on this phase

This phase removes the plaintext `PING/PONG` bootstrap path and replaces it with a minimal **TriTRPC v1** runtime binding for internal service health traffic. The upstream `SocioProphet/TriTRPC` repository remains the normative transport source of truth; this repository only defines the platform-specific stream binding and deployment profile around that standard.
