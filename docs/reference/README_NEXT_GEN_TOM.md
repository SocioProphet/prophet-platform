# Next Gen TOM Documentation Bundle

This bundle documents the corrected v2 model derived from the slide set analyzed in this chat. It is organized for direct lift into a repository such as `prophet-platform`.

## Contents

- `docs/reference/operating-model/next-gen-tom-raci-v2.md`  
  Full 30-capability RACI, operating placement, governance bodies, and handoff rules.
- `docs/reference/architecture/brokerage-reference-architecture-v2.md`  
  Brokerage-centered ITaaS reference architecture, planes, providers, objects, APIs, events, and control gates.
- `docs/reference/operations/operating-cadence-kpi-model-v1.md`  
  Operating cadence, evidence cadence, journey-facing metrics, and benefits realization signals for all 30 capabilities.
- `docs/reference/economics/ng-tom-benefits-instrumentation-v1.md`  
  Benefit model, realization rules, and minimum instrumentation expectations.
- `specs/brokerage/schemas/`  
  JSON Schema starter package for the canonical brokerage objects and event envelope.
- `specs/brokerage/lifecycles/`  
  State models and transition rules.
- `specs/brokerage/interfaces/`  
  API surface, event surface, and policy hook definitions.

## Canonical statement

The Next Gen TOM is a brokerage-centered, hybrid-cloud, ITaaS-style operating model that organizes technology through five structural domains:

1. Engage
2. Orchestrate
3. Provision
4. Service
5. Control

Value is measured through separate structural, benefits, and journey views. The package keeps those views distinct so the model does not collapse into a single false taxonomy.


## v2 extension set

This v2 package adds:
- a docs index for repository landing
- an OpenAPI surface for the brokerage resource model
- lifecycle transition guards and benefit-credit guard rules
- provider-class overlays for internal shared services, public cloud, SaaS, partner services, and legacy adapters
- example event and object payloads
- a local schema validation runner for the included examples
