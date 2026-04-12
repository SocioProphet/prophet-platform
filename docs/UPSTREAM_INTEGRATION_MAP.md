# Upstream Integration Map for Current Prophet Work

This document records where the current sandboxed work should land across upstream repositories.

It exists to prevent the same mistake from recurring:

> a large amount of valid platform work gets produced, but it has no canonical upstream home and therefore no executable future.

## Current workstreams

### 1. Fabric / deployment / HA-DR / local bootstrap
**Canonical home:** `SocioProphet/prophet-platform`

Why:
- this repo is the runtime and deployment hub
- it already defines `apps/`, `contracts/`, `docs/`, `infra/`, `tools/`, and local dev/eval fabric guidance
- local thin-slice and cluster bootstrap belong with runtime truth, not with public surfaces

What should land here over time:
- local Compose bootstrap
- kind / k3d bootstrap
- thin-slice services
- chart wiring for thin-slice services
- smoke tests and local validation helpers
- time-series ML plane docs and runtime bindings

### 2. CLI façade / operator workflow
**Canonical home:** `SocioProphet/prophet-cli`

Why:
- this repo is explicitly the façade repo for Prophet command surfaces and SourceOS bootstrap delegation
- command semantics should not be smeared across the runtime repo

What should land here over time:
- `prophet dev up/status/destroy`
- `prophet train run`
- `prophet model register/promote`
- `prophet infer`
- shell/JSON output modes for agent use
- delegation glue into `prophet-platform` scripts or workflows

### 3. Public docs / public surface / marketing integration
**Canonical home:** `SocioProphet/socioprophet`

Why:
- this repo is the public surfaces + integration workspace
- it should document and reference platform capabilities, not become the runtime home for them

What may land here:
- public-facing pages describing Prophet Platform
- integration docs for how SocioProfit and other apps consume Prophet
- links to runtime docs in `prophet-platform`

### 4. Standards / doctrine / schemas
**Canonical homes:** standards repos such as `SocioProphet/socioprophet-standards-storage` and related doctrine homes

Why:
- platform runtime repos should not become the only source of truth for portable doctrine
- contracts that need to survive across repos should be elevated into standards repos once stable

## Current sandbox artifact mapping

### Artifact family: platform fabric / local dev / MLOps / time-series docs
**Immediate canonical placement:** `prophet-platform`

Use the sandbox artifacts as source material for:
- `docs/LOCAL_DEV_THIN_SLICE.md`
- `docs/TIME_SERIES_ML_PLANE.md`
- future `infra/local/` bootstrap files
- future `apps/` thin-slice services
- future `tools/` smoke targets

### Artifact family: CLI-facing lifecycle
**Immediate canonical placement:** `prophet-cli`

Use the sandbox artifacts as source material for:
- command docs
- command parser scaffolding
- delegation model to runtime repo scripts/workflows

## Placement doctrine

When in doubt:
- runtime + deployment truth -> `prophet-platform`
- command façade -> `prophet-cli`
- public docs/integration surface -> `socioprophet`
- portable doctrine/specs -> standards repos

That split is the current canonical interpretation.
