# eval-fabric-api

FastAPI surface for the Prophet Platform evaluation, observability, and intelligence lane.

## Canonical runtime

The default runtime is the **unified** application path:
- `/healthz` — process liveness only
- `/readyz` — Postgres + ClickHouse readiness
- `/v1/frontier` — profile-score frontier view (ClickHouse)
- `/v1/models/{model_release_id}/dossier` — model dossier facts (ClickHouse)
- `/v1/competition/radar` — competitor radar view (Postgres)

The default Dockerfile and default local compose stack point at this runtime.

## Receipt / evidence emission

When `EVAL_FABRIC_EMIT_RECEIPTS=1`, business routes emit local platform artifacts:
- payload artifact
- `EventEnvelope`
- `EvidenceReceipt`

The API returns file refs for these artifacts in response headers:
- `X-Payload-Ref`
- `X-Event-Envelope-Ref`
- `X-Evidence-Receipt-Ref`

## Retained variants

The repo may still carry alternate files such as `persisted_main.py` or alternate Dockerfiles during transition, but the platform default is the unified path, not the seeded demo path.

## Tests

This lane is backed by:
- route tests
- repository parameterization tests
- schema validation tests
- receipt emission tests
- a compose-backed smoke test
