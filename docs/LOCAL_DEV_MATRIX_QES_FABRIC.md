# Local Dev — Matrix/QES Fabric

This runbook is the first local path for the Matrix/QES lane.

## Scope of this slice

The first slice is intentionally narrow:
- thin Matrix operator HTTP surface
- deterministic room/thread state machine
- SQLite-backed thread state for restart tolerance
- canonical QES event contracts checked into `contracts/qes/events/`

It does **not** yet include:
- live Matrix homeserver binding
- live Kafka/Redpanda publishing
- live PostgreSQL or ClickHouse adapters
- Temporal-backed replay workers

Those belong in the next integration-hardening slices.

## Environment

Optional environment variables:
- `SOCIOPROFIT_STATE_HOME` — override local platform state root
- default local state root: `~/.local/state/prophet-platform`

The operator service persists thread state under the platform state root, consistent with the thin state conventions already used in other apps.

## Local setup

```bash
cd apps/matrix-qes-operator && test -d .venv || python3 -m venv .venv && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt -r requirements-test.txt
```

## Run tests

```bash
cd apps/matrix-qes-operator && . .venv/bin/activate && pytest -q tests
```

## Run the service

```bash
cd apps/matrix-qes-operator && . .venv/bin/activate && uvicorn app.main:app --reload --port 8091
```

## Useful routes

- `GET /healthz`
- `GET /v1/matrix-qes/transitions`
- `POST /v1/matrix-qes/commands/parse`
- `POST /v1/matrix-qes/commands/apply`

## Example command parse

```bash
curl -s http://127.0.0.1:8091/v1/matrix-qes/commands/parse \
  -H 'content-type: application/json' \
  -d '{
    "actor": "@ops:example.org",
    "room_id": "!incident:example.org",
    "thread_id": "$thread1",
    "body": "!qes ack"
  }'
```

## Example command apply

```bash
curl -s http://127.0.0.1:8091/v1/matrix-qes/commands/apply \
  -H 'content-type: application/json' \
  -d '{
    "actor": "@ops:example.org",
    "room_id": "!incident:example.org",
    "thread_id": "$thread1",
    "body": "!qes replay.request dry-run"
  }'
```

## Expected behavior

- commands must begin with `!qes`
- unknown verbs fail fast
- invalid state transitions return an error response
- valid transitions are persisted for the room/thread key

## Next steps

1. Bind the service to a real Matrix homeserver client.
2. Project successful operator actions into replay requests and event-bus emission.
3. Add OpenFeature-compatible resolution snapshots and a same-origin QES gateway.
