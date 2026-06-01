# DevSecOps Workroom Validator Semantics v0.1

Status: canonical semantic validation note  
Plane: Prophet Platform contract validation  
Parent: `docs/architecture/devsecops-intelligence-workroom-v0.1.md`

## Purpose

This note records the validation boundary for the DevSecOps Intelligence Workroom v0.1.

The JSON Schema in `contracts/workroom/devsecops-workroom-v0.1.schema.json` defines structural shape and portable field vocabulary.

The Python validator in `tools/validate_devsecops_workroom.py` is the canonical semantic gate for v0.1 fixture correctness.

Downstream consumers must not treat JSON Schema validation alone as sufficient workroom validity.

## Canonical validator

The canonical v0.1 semantic validator is:

```text
tools/validate_devsecops_workroom.py
```

It validates:

- JSON Schema shape via `jsonschema.Draft202012Validator`;
- lane-specific source reference requirements;
- validation evidence state and runtime parity compatibility;
- verified receipt reference and provenance binding;
- post-merge incident topology and blast-radius context;
- topology snapshot evidence provenance;
- behavioral event source-lane consistency;
- evidence refs referenced by events and claims;
- RCA claim evidence requirements;
- confirmed causal claim counterevidence handling;
- action grant approval posture;
- remediation risk/action-grant binding;
- expected-invalid fixture failure reasons.

## Lane-specific requirements

### Pre-merge validation lane

A `pre_merge_validation` workroom record must include:

- `source_refs.change_set_ref`;
- `source_refs.environment_request_ref`;
- `source_refs.validation_run_ref`;
- `validation_evidence_state`.

Evidence-state compatibility:

- `not_configured`, `selected_only`, and `missing_evidence` require `runtime_parity_level: contract_only`;
- `synthetic_observed` requires `runtime_parity_level: synthetic_observed`;
- `verified_receipt` requires `runtime_parity_level: runtime_observed`;
- `failed_receipt` and `stale_receipt` require receipt references but do not certify parity.

A `runtime_observed` record must include:

- `validation_evidence_state: verified_receipt`;
- `source_refs.validation_receipt_ref`;
- runtime receipt evidence whose `provenance.source_ref` matches that receipt ref.

### Post-merge incident lane

A `post_merge_incident` workroom record must include:

- `source_refs.incident_ref`;
- `source_refs.investigation_run_ref`;
- `source_refs.topology_ref`;
- `source_refs.blast_radius_ref`.

It must also include topology evidence:

- at least one `evidence_type: topology_snapshot` packet;
- its `provenance.source_ref` must match `source_refs.topology_ref`.

Post-merge incident event types are limited to:

- `production_incident`;
- `post_deploy_degradation`;
- `customer_impact_event`.

## Event model note

`pre_merge_validation_verified` is the v0.1 event type for verified pre-merge validation receipts.

This avoids encoding verified validation as `pre_merge_validation_failure`.

The event remains under `behavioral_divergence_event` in v0.1 for compatibility. A later v0.2 may split successful validation outcomes into a sibling `ValidationOutcomeEvent`.

## RCA claim discipline

Claim statuses are:

- `observation`;
- `hypothesis`;
- `supported_causal_claim`;
- `confirmed_causal_claim`;
- `falsified_claim`;
- `unknown`.

Rules:

- `supported_causal_claim` and `confirmed_causal_claim` require evidence references.
- `confirmed_causal_claim` also requires counterevidence handling.
- `unknown` requires `confidence: none`.
- A claim that references evidence not present in the record fails validation.

## Action and remediation discipline

Mutation-class actions include:

- `diagnostic_mutation`;
- `reversible_mitigation`;
- `irreversible_mutation`;
- `credential_sensitive`;
- `data_sensitive`;
- `customer_visible`;
- `destructive`;
- `privileged_identity`;
- `network_exposure`;
- `production_change`.

A mutation-class action must not be `allowed` without an approval requirement.

High and critical remediation plans require action-grant references.

## Non-claims

This validation model does not execute live sandbox infrastructure.

This validation model does not certify Signadot-style runtime feature parity.

This validation model does not authorize production remediation.

This validation model does not replace Sociosphere, AgentPlane, GAIA, Guardrail Fabric, or ProCybernetica ownership of their respective planes.
