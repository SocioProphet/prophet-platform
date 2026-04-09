# eval-fabric-api

Thin FastAPI starter for the Prophet Platform evaluation, observability, and intelligence lane.

Current routes:
- `/healthz`
- `/v1/frontier`
- `/v1/models/{model_release_id}/dossier`
- `/v1/competition/radar`

## Default local/runtime path

The preferred local development path is now the **unified DB-backed** entrypoint:
- container: `Dockerfile.unified`
- compose: `infra/local/docker-compose.eval-fabric.unified.yml`
- app entrypoint: `app/unified_main.py`

Legacy seeded and intermediate persisted variants remain in the repo as bootstrap history, but the unified path is the visible default for platform work going forward.
