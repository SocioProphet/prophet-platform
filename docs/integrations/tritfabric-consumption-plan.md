# TritFabric consumption plan

## Status

Planning and contract-registration tranche only.

This document records how Prophet Platform should consume TritFabric Community Learning, Network Atlas, model-card promotion, and Serve-readiness surfaces without importing TritFabric implementation or claiming runtime readiness.

## Upstream sources

- TritFabric implementation and contracts: `SocioProphet/tritfabric`
- Sociosphere estate registration: `SocioProphet/sociosphere`
- Ontogenesis vocabulary and SHACL gates: `SocioProphet/ontogenesis`

## Product surfaces

### Community Learning intake

Prophet Platform may expose product-facing workflows for collecting feedback, curation records, curriculum evaluations, and proposal records only after the upstream gates are enforced:

- consent required;
- license required;
- lineage required;
- rubric required;
- manual review required before promotion.

No Prophet Platform route should train a model, mutate a model, or promote an artifact directly from community intake.

### Network Atlas framework catalog

Prophet Platform may present framework catalog entries and capability descriptors as product navigation surfaces. Catalog status must remain claim-bounded:

- `raw_source`, `candidate`, `planned`, and `stubbed` are not validated adapter claims;
- adapter support requires implementation and conformance tests in the owning repo;
- license and maintenance status must be visible where relevant.

### Model-card promotion

Prophet Platform may display model-card promotion evidence. Promotion evidence must carry:

- `mathType`;
- `calcOps`;
- `ledgerRef`;
- `artifactRef`.

Transport-visible status should be represented as TRUE / MID / FALSE with machine-readable reason strings.

### Serve readiness

Prophet Platform may display Serve autoscaler readiness and metrics only as readiness evidence unless a later runtime deployment tranche lands.

The current permitted posture is readiness/reporting, not production autoscaling.

## Non-goals

This tranche does not implement product APIs.

This tranche does not ingest TritFabric events.

This tranche does not call TritFabric services.

This tranche does not execute community workflows.

This tranche does not claim validated framework adapters.

This tranche does not deploy Serve autoscaling.

## Acceptance gates for future runtime consumption

1. Product routes must preserve consent/license/lineage/rubric gates.
2. Product UI must distinguish catalog intake records from validated adapters.
3. Promotion surfaces must preserve Trit status and evidence references.
4. Serve surfaces must label readiness versus active runtime deployment.
5. Ontogenesis terms should be used for product vocabulary once stable.

## Claim boundary

Prophet Platform is a consumer of governed surfaces. It is not the authority plane for TritFabric contracts, Ontogenesis vocabulary, or Sociosphere estate registration.
