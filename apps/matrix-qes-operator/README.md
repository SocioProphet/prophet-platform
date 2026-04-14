# matrix-qes-operator

Thin Matrix operator-facing control surface for the platform Matrix/QES lane.

## Why it exists

The platform now needs a narrow, reviewable place to make these behaviors real:
- deterministic Matrix room/thread lifecycle handling
- `!qes` operator command parsing
- replay-request intent capture before full workflow binding
- durable thread state across process restarts

This service is intentionally **thin**.

It does not yet:
- speak to a live Matrix homeserver
- publish to Kafka/Redpanda
- execute replay workflows
- persist into PostgreSQL / ClickHouse

Those integrations belong in subsequent slices once the contract seam is stable.

## Endpoints

- `/healthz`
- `/v1/matrix-qes/transitions`
- `/v1/matrix-qes/commands/parse`
- `/v1/matrix-qes/commands/apply`

## State handling

The service persists room/thread lifecycle state under the platform state root so the lifecycle survives restarts and remains compatible with existing thin local-state patterns in `prophet-platform`.
