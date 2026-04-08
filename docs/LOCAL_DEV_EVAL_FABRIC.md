# Local Dev Runbook: Evaluation Fabric

This runbook stands up the local platform services for the evaluation and intelligence lane.

## Services

The initial local stack includes:
- `postgres` for control-plane and transactional metadata
- `clickhouse` for analytical metric facts and score views
- `eval-fabric-api` for seeded frontier, dossier, radar, and health routes

## Start the local stack

From the repo root:

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.yml up --build
```

## Health checks

After startup:
- API health: `http://localhost:8080/healthz`
- Frontier endpoint: `http://localhost:8080/v1/frontier`
- Dossier endpoint: `http://localhost:8080/v1/models/model.semantic-stack.2026-04-05/dossier`
- Radar endpoint: `http://localhost:8080/v1/competition/radar`

## Notes

- This lane is seeded and intentionally thin.
- The API currently returns stable seeded payloads suitable for wiring the first dashboard views.
- The next implementation step is replacing seeded payloads with persisted reads from Postgres and ClickHouse.

## Stop the stack

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.yml down -v
```
