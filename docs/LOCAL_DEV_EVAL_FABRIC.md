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

## Notes

- The unified local path reads from Postgres and ClickHouse seed state.
- Older compose variants remain in the repo as bootstrap history, but the unified path is the visible default going forward.
- The next implementation step is replacing seed SQL and direct query logic with migrations, adapters, and ingestion workers.

## Stop the stack

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.unified.yml down -v
```
