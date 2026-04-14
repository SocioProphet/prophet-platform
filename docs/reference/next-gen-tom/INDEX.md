# Next Gen TOM Documentation Index

This package captures the normalized operating model, brokerage architecture, cadence/KPI model,
benefits instrumentation, and the implementation-grade contract surface for the hybrid-cloud,
brokerage-centered ITaaS operating model.

## Core references
- `raci.md` — 30-capability RACI, governance bodies, placement model, and exception authority.
- `brokerage-architecture.md` — six-plane brokerage architecture, canonical records, policy hooks, and control gates.
- `cadence-kpi-model.md` — management cadences, KPI families, evidence rhythms, and benefits realization signals.
- `benefits-instrumentation.md` — benchmark-cap interpretation, benefit-credit gates, and instrumentation model.

## Implementation contracts
- `../../../specs/brokerage/schemas/` — JSON Schema starters for core brokerage objects and event envelope.
- `../../../specs/brokerage/openapi/brokerage-api-v1.yaml` — OpenAPI surface for the resource model.
- `../../../specs/brokerage/validation/transition-guards.md` — lifecycle transition guards and acceptance rules.
- `../../../specs/brokerage/events/examples/` — example event payloads and object examples.

## Tooling
- `../../../tools/validate_examples.py` — local schema validation runner for the included examples.
