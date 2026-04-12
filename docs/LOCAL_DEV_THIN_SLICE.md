# Local Dev Thin Slice for Prophet Platform

This document integrates the current **thin-slice developer workflow** into `prophet-platform` as the canonical runtime/deployment lane for local bootstrapping.

## Why this exists

`prophet-platform` is the runtime and deployment hub for the platform. The thin slice gives us the smallest executable path that proves the following lifecycle on a disposable local node:

1. build local images
2. start a minimal control plane
3. start a minimal query gateway
4. train one model from code + spec
5. write an artifact
6. register the model
7. promote the model to `prod`
8. resolve and infer through the gateway

This is intentionally smaller than the full platform. It is the **golden closure path** we use to turn platform theory into executable truth.

## Thin-slice services

The current thin slice consists of:

- `prophet-control-plane`
- `prophet-query-gateway`
- `prophet-trainer`

These are not the whole platform. They are the minimum set required to prove the local developer loop.

## Modes

### Compose-first
Use Docker Compose when iterating on:
- specs
- trainer code
- model artifact handling
- control-plane and query-gateway contracts

This is the fastest inner loop.

### kind / k3d next
After Compose passes, the same thin slice should be runnable on:
- `kind` for CI-faithful local Kubernetes
- `k3d` for lightweight k3s-style local testing

## Canonical local workflow

The intended workflow is:

```bash
make compose-build && make compose-up && ./scripts/e2e_local.sh
```

The long-term target is a single command such as:

```bash
make e2e-local
```

that performs:
- image build
- service boot
- train -> register -> promote -> infer
- assertion and teardown

## Relationship to other repos

- `prophet-platform` owns the runtime/deployment side of this workflow.
- `prophet-cli` owns the command façade and operator/developer command surface.
- `socioprophet` remains a public surfaces/integration repo, not the canonical runtime home for this lane.

## What is intentionally out of scope here

This document does **not** define the full production platform.
It does **not** claim the thin slice is equivalent to the full HA/DR mesh or full MLOps stack.
It defines the minimum executable closure path that future work must preserve.

## Next integration steps

1. land the actual thin-slice service code in `apps/` under this repo
2. land local `infra/local/` bootstrap files for Compose and kind/k3d
3. add a `tools/` smoke target that asserts the thin slice works from code and spec only
4. wire this same path into CI before expanding the platform surface
