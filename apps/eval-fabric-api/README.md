# eval-fabric-api

FastAPI surface for the Prophet Platform evaluation, observability, and intelligence lane.

## Canonical runtime

The canonical runtime entrypoint is `app.main`.

It owns:
- `/healthz` — process liveness only
- `/readyz` — Postgres + ClickHouse readiness
- `/v1/frontier`
- `/v1/frontier/provenance`
- `/v1/models/{model_release_id}/dossier`
- `/v1/models/{model_release_id}/attribution`
- `/v1/runs/{run_id}/provenance`
- `/v1/governance/crosswalks`
- `/v1/competition/reproduced-vs-claimed`
- `/v1/competition/radar`

`app.unified_main` remains only as a compatibility wrapper so existing imports do not break while the runtime consolidates on one entrypoint.

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

New eval-fabric emissions use the platform **type-first** layout:
- `prophet-platform/payloads/eval-fabric-api/`
- `prophet-platform/events/eval-fabric-api/`
- `prophet-platform/receipts/eval-fabric-api/`

The reader still supports the legacy service-first layout for historical compatibility, but new producer output should use the canonical path above.

## Tests

This lane is backed by:
- route tests against `app.main`
- repository parameterization tests
- schema validation tests
- receipt emission tests
- a compose-backed smoke test
