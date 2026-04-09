# Local Dev Runbook: Evaluation Fabric

This runbook stands up the local platform services for the evaluation and intelligence lane.

## Services

The initial local stack includes:
- `postgres` for control-plane and transactional metadata
- `clickhouse` for analytical metric facts and score views
- `eval-fabric-api` for frontier, dossier, radar, and health routes backed by the canonical unified runtime

## Start the local stack

From the repo root:

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.yml up --build
```

## Health checks

After startup:
- Liveness: `http://localhost:8080/healthz`
- Readiness: `http://localhost:8080/readyz`
- Frontier endpoint: `http://localhost:8080/v1/frontier`
- Dossier endpoint: `http://localhost:8080/v1/models/model.semantic-stack.2026-04-05/dossier`
- Radar endpoint: `http://localhost:8080/v1/competition/radar`

## Notes

- The default local stack should now use the unified repository-backed runtime.
- Postgres and ClickHouse are seeded for deterministic local smoke checks.
- The next implementation step is wiring this lane into platform event/evidence receipts and dashboard surfaces.

## Stop the stack

```bash
cd "$HOME/dev/prophet-platform" && docker compose -f infra/local/docker-compose.eval-fabric.yml down -v
```
