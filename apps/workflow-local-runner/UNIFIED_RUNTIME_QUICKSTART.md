# Workflow Local Runner — Unified Runtime Quickstart

Preferred runtime-facing entrypoint:

- `app/unified_main.py`

## Routes

- `GET /healthz`
- `POST /v1/runs/local-execute`
- `POST /v1/bundles/{service}/{correlation_id}/materialize`
- `POST /v1/runs/local-execute-bound`

## Guidance

- Use `unified_main.py` for operator-facing integration and tests.
- Treat `main.py`, `materialize_main.py`, and `execute_bound_main.py` as implementation modules unless a lower-level test specifically needs them.
- Use the existing `evidence-receipts` service to inspect the payload/event/receipt side of a run.
- Use the bound-bundle materialization path when you need the richer derived bundle artifact.

## Related notes

- `CANONICAL_RUNTIME_SURFACE.md`
- `README.md`
