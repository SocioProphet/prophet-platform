# eval-fabric-api

FastAPI surface for the Prophet Platform evaluation, observability, and intelligence lane.

## Canonical runtime

The default runtime is now the **unified** application path:
- `/healthz` — process liveness only
- `/readyz` — Postgres + ClickHouse readiness
- `/v1/frontier` — profile-score frontier view (ClickHouse)
- `/v1/models/{model_release_id}/dossier` — model dossier facts (ClickHouse)
- `/v1/competition/radar` — competitor radar view (Postgres)

The default Dockerfile and default local compose stack should point at this runtime.

## Retained variants

The repo may still carry alternate files such as `persisted_main.py` or alternate Dockerfiles during transition, but the platform default should be the unified path, not the seeded demo path.

## Tests

This lane should be backed by:
- route tests
- repository parameterization tests
- schema validation tests
- a compose-backed smoke test
