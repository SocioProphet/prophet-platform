# Local Dev Runbook: Evaluation Fabric

This runbook stands up the local platform services for the evaluation and intelligence lane.

## Services

The default local stack includes:
- `postgres` for control-plane and transactional metadata
- `clickhouse` for analytical metric facts and score views
- `eval-fabric-api` for DB-backed frontier, dossier, radar, and health routes

## Start the local stack

From the repo root:

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.unified.yml up --build
```

## Health checks

After startup:
- API health: `http://localhost:8082/healthz`
- Frontier endpoint: `http://localhost:8082/v1/frontier`
- Dossier endpoint: `http://localhost:8082/v1/models/model.semantic-stack.2026-04-05/dossier`
- Radar endpoint: `http://localhost:8082/v1/competition/radar`
- Liveness: `http://localhost:8080/healthz`
- Readiness: `http://localhost:8080/readyz`
- Frontier endpoint: `http://localhost:8080/v1/frontier`
- Dossier endpoint: `http://localhost:8080/v1/models/model.semantic-stack.2026-04-05/dossier`
- Radar endpoint: `http://localhost:8080/v1/competition/radar`

## Receipt / evidence emission

The default local stack enables receipt emission for business routes:
- `EVAL_FABRIC_EMIT_RECEIPTS=1`
- `SOCIOPROFIT_STATE_HOME=/tmp/prophet-platform-state`

Business responses expose file refs in these headers:
- `X-Payload-Ref`
- `X-Event-Envelope-Ref`
- `X-Evidence-Receipt-Ref`

These refs point to artifacts written inside the container under `/tmp/prophet-platform-state/prophet-platform/eval-fabric-api/`.

## Notes

- The unified local path reads from Postgres and ClickHouse seed state.
- Older compose variants remain in the repo as bootstrap history, but the unified path is the visible default going forward.
- The next implementation step is replacing seed SQL and direct query logic with migrations, adapters, and ingestion workers.
- The default local stack uses the unified repository-backed runtime.
- Postgres and ClickHouse are seeded for deterministic local smoke checks.
- The next implementation step is wiring these emitted artifacts into broader platform event/evidence consumers and dashboard surfaces.

## Stop the stack

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.unified.yml down -v
```
