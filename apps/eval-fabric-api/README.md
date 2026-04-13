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
The default runtime is the **unified** application path:
- `/healthz` — process liveness only
- `/readyz` — Postgres + ClickHouse readiness
- `/v1/frontier` — profile-score frontier view (ClickHouse)
- `/v1/models/{model_release_id}/dossier` — model dossier facts (ClickHouse)
- `/v1/competition/radar` — competitor radar view (Postgres)

The default Dockerfile and default local compose stack point at this runtime.

## Receipt / evidence emission

When `EVAL_FABRIC_EMIT_RECEIPTS=1`, business routes emit local platform-style artifacts:
- payload artifact
- `EventEnvelope`
- `EvidenceReceipt`

Responses expose file refs in these headers:
- `X-Payload-Ref`
- `X-Event-Envelope-Ref`
- `X-Evidence-Receipt-Ref`

### Canonical artifact layout

New eval-fabric emissions now use the platform **type-first** layout:
- `prophet-platform/payloads/eval-fabric-api/`
- `prophet-platform/events/eval-fabric-api/`
- `prophet-platform/receipts/eval-fabric-api/`

The reader still supports the legacy service-first layout for historical compatibility, but new producer output should use the canonical path above.

## Retained variants

The repo may still carry alternate files such as `persisted_main.py` or alternate Dockerfiles during transition, but the platform default is the unified path, not the seeded demo path.

## Tests

This lane is backed by:
- route tests
- repository parameterization tests
- schema validation tests
- receipt emission tests
- a compose-backed smoke test
