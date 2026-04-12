# Local Runtime Bootstrap (Canonical Landing Zone)

This directory is the canonical landing zone for **local runtime bootstrap** assets owned by `prophet-platform`.

It exists so that local development and thin-slice execution do not live only in sandbox exports or detached branches.

## What belongs here

Examples of files that should land here over time:

- `docker-compose.*.yml` for local bootstrap
- `kind` cluster config
- `k3d` cluster config
- local image-loading helpers
- local network / port mapping notes
- bootstrap shell scripts used by `prophet-cli`

## What should not live only here

This directory holds runtime bootstrap assets, but their command façade should be exposed through `prophet-cli`.

That means:
- `prophet-platform` owns the actual files and runtime behavior
- `prophet-cli` owns the end-user/operator command entrypoints

## Thin-slice rule

Before full-platform local bootstrap becomes complex, the first target is a **thin-slice local closure path**:

- build images
- bring up minimal services
- train -> register -> promote -> infer
- destroy disposable environment

That path should remain the first-class truth path for local development.
