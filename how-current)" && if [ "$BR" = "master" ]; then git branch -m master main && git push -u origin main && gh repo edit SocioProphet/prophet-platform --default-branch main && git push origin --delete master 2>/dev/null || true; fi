# Prophet Platform (SocioProphet)

This repository is the **platform/infrastructure management hub** for SocioProphet.

It is intentionally structured as a **thin platform monorepo**:
- `apps/` contains deployable services (API, gateway, web portal, etc.)
- `infra/` contains deployment wiring (Kustomize, Argo CD appsets, namespaces, etc.)
- `docs/` contains platform-level guidance (architecture, security, roadmap)
- `rpc/` contains triRPC contracts used by apps and tooling
- `schemas/` contains data/format schema references

## Why this repo exists

We keep **standards** and **governance** in dedicated standards repos (e.g. storage standards),
and we keep **shipping platform code + infra wiring** here. This avoids a standards repo
accidentally becoming a monolith while still giving us one coherent place to run/operate the platform.

## Quickstart

```bash
make validate
```

## Reading order

1) `docs/ARCHITECTURE.md`
2) `docs/SECURITY.md`
3) `rpc/`
4) `infra/k8s/`

## Notes on this seed

This repo was seeded from an older infrastructure/platform scaffold. We preserved useful patterns
(Argo CD + Kustomize, API/gateway split, portal wiring) and added a standards-style validation gate.
