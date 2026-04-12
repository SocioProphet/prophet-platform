# Fog Stack Evaluation (initial upstream slice)

This document records the minimal initial landing for **Fog Stack Evaluation** inside `prophet-platform`.

## Runtime anchors

Fog Stack Evaluation is grounded in existing platform evaluation fabric surfaces:
- `apps/eval-fabric-api` — platform evaluation and monitoring API surface
- `infra/datastores/postgres/` — transactional and control-plane state
- `infra/datastores/clickhouse/` — analytical metric facts and ranking views
- `docs/PLATFORM_EVAL_FABRIC.md` — platform-owned evaluation, observability, and intelligence lane

This means the offering is currently anchored in the substrate's `cluster-service` class.

## Upstream artifacts in this slice

- `bundles/fogstack.evaluation-v0.1.yaml`
- `conformance/rulepacks/fogstack.evaluation-v0.1.yaml`

## Why this is the third staged slice

The initial Access slice establishes the verifier path and bundle/rulepack layout.
The Knowledge slice proves a multi-runtime-class offering.
Evaluation follows after those two because it is the first offering whose substrate meaning depends on the platform-owned evaluation fabric lane and its datastore split.

## What remains sandbox-only for now

The following remain in sandbox incubation until this third slice is accepted:
- operator pack
- compatibility matrix and machine-readable compatibility policy object
- pass/fail bundle examples and generated result JSON
- broader catalog/lifecycle promotion

## Intended next step

After this slice is accepted, the next work should shift from adding offerings to strengthening bundle release discipline and machine-readable lifecycle/support metadata upstream.
