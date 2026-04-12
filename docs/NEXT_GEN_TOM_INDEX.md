# Next Gen TOM Documentation Index

This package captures the normalized operating model, brokerage architecture, cadence/KPI model,
benefits instrumentation, and the implementation-grade contract surface for the hybrid-cloud,
brokerage-centered ITaaS operating model.

## Core references
- `reference/operating-model/next-gen-tom-raci-v2.md` — 30-capability RACI, governance bodies, placement model, and exception authority.
- `reference/architecture/brokerage-reference-architecture-v2.md` — six-plane brokerage architecture, canonical records, policy hooks, and control gates.
- `reference/operations/operating-cadence-kpi-model-v1.md` — management cadences, KPI families, evidence rhythms, and benefits realization signals.
- `reference/economics/ng-tom-benefits-instrumentation-v1.md` — benchmark-cap interpretation, benefit-credit gates, and instrumentation model.

## Implementation contracts
- `../specs/brokerage/schemas/` — JSON Schema starters for core brokerage objects and event envelope.
- `../specs/brokerage/openapi/brokerage-api-v1.yaml` — OpenAPI surface for the resource model.
- `../specs/brokerage/interfaces/` — API, event, and policy-hook descriptions.
- `../specs/brokerage/lifecycles/` — state machine summaries.
- `../specs/brokerage/validation/transition-guards.md` — lifecycle transition guards and acceptance rules.
- `../specs/brokerage/provider-overlays/` — provider-class overlays for internal shared services, public cloud, SaaS, partner services, and legacy adapters.
- `../specs/brokerage/events/examples/` — example event payloads and object examples.

## Tooling
- `../tools/validate_examples.py` — local schema validation runner for the included examples.

## Usage intent
This package is intended to be dropped into the platform repository as a design baseline.
It is implementation-neutral on transport/runtime but concrete about objects, states, events,
policy hooks, evidence obligations, and economics metadata.
