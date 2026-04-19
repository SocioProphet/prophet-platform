# Workflow Local Runner Examples

This examples lane is for consumers of the unified runtime shell.

Preferred runtime-facing entrypoint:

- `app/unified_main.py`

## Routes covered here

- `POST /v1/runs/local-execute`
- `POST /v1/bundles/{service}/{correlation_id}/materialize`
- `POST /v1/runs/local-execute-bound`

## Files

- `local_execute.request.v0.1.json`
- `local_execute.response.v0.1.json`
- `materialize.response.v0.1.json`
- `local_execute_bound.request.v0.1.json`
- `local_execute_bound.response.v0.1.json`

## Guidance

Use these examples against the unified shell unless a lower-level test explicitly needs one of the implementation modules.
