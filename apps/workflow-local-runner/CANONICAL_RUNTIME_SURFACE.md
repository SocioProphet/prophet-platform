# Workflow Local Runner — Canonical Runtime Surface

Status: Active

Canonical runtime entrypoint: `apps/workflow-local-runner/app/unified_main.py`

## Purpose

This note records the intended runtime surface for the local runner after the staged additive build-out.

The canonical API shell is now the unified entrypoint, which exposes:

- `GET /healthz`
- `POST /v1/runs/local-execute`
- `POST /v1/bundles/{service}/{correlation_id}/materialize`
- `POST /v1/runs/local-execute-bound`

## Entrypoint roles

### Canonical

- `app/unified_main.py`
  - The preferred operator- and integration-facing runtime shell.
  - Presents one API surface for execute, materialize, and execute-and-materialize flows.

### Internal implementation modules

- `app/main.py`
  - Base local execution writer.
  - Emits payload, event, receipt, and catalog artifacts.

- `app/materialize_bound_bundle.py`
  - Pure helper that projects local-runner state into the richer bound-bundle artifact.

- `app/materialize_main.py`
  - Materialization API over an existing receipt bundle.

- `app/execute_bound_main.py`
  - Execute-and-materialize adapter used by the unified API shell.

## Policy

New integration points SHOULD target `unified_main.py` unless there is a specific need to test or reuse one of the lower-level implementation modules.

Lower-level entrypoints remain present to preserve incremental tests and staged composition, but they SHOULD be treated as implementation detail rather than primary runtime contract.

## Relationship to standards

This runtime surface is constrained by:

- the workbench/run/receipt binding appendix in `socioprophet-standards-storage`
- the workbench schema family and projection layer in `sociosphere`
- the existing `evidence-receipts` service state layout in `prophet-platform`

## Follow-on cleanup

When a safe existing-file update path is available, the remaining cleanup tasks are:

1. fold primary workbench index discoverability into the canonical `sociosphere` index file
2. optionally collapse lower-level runtime entrypoints further if doing so does not reduce test clarity
