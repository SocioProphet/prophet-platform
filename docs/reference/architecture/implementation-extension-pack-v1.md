# Next Gen TOM Implementation Extension Pack v1

This addendum extends the original documentation package with implementation-grade material intended to reduce drift between operating-model prose and platform contracts.

## Additions in this extension pack

1. **Documentation index**
   - Adds `docs/INDEX.md` so the package can land in-repo with a clean entry point.

2. **OpenAPI surface**
   - Adds `specs/brokerage/openapi/brokerage-api-v1.yaml` to formalize the core resource model.
   - Covers offerings, blueprints, providers, requests, policy decisions, fulfillment orders, instances, exceptions, evidence packs, and cost meters.

3. **Transition guards**
   - Adds `specs/brokerage/validation/transition-guards.md` with allowed state transitions and hard guard conditions.
   - Includes benefit-credit gates so economics are only booked when the automated path has truly displaced manual work.

4. **Provider overlays**
   - Adds provider-specific overlays for internal shared services, public cloud, SaaS, partner services, and legacy adapters.
   - These overlays capture the control and evidence deltas that the base object model alone does not express.

5. **Examples and validation tooling**
   - Adds example request, instance, and event payloads.
   - Adds `tools/validate_examples.py` as a local validator against the included JSON Schemas.

## Why this matters

The original package was structurally strong, but it still left room for implementation drift.
This extension narrows that gap by moving the design one step closer to a contract surface that can be validated,
implemented, and reviewed by engineering, platform, service-operations, and control stakeholders.

## Recommended repository landing

- `docs/INDEX.md`
- `docs/reference/...`
- `specs/brokerage/openapi/brokerage-api-v1.yaml`
- `specs/brokerage/provider-overlays/*.md`
- `specs/brokerage/validation/transition-guards.md`
- `specs/brokerage/events/examples/*.json`
- `tools/validate_examples.py`

## Recommended next move

Bind the OpenAPI and JSON Schema layer to CI so that event examples and object examples are validated automatically.
After that, generate provider-specific policy packs and transition checks from the same source vocabulary.
