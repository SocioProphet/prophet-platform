# DevSecOps Workroom Parity Ledger v0.1

Status: parity ledger and claim boundary  
Plane: Prophet Platform / cross-plane DevSecOps Intelligence Workroom  
Parent: `docs/architecture/devsecops-intelligence-workroom-v0.1.md`

## Purpose

This ledger defines what the estate may and may not claim as the DevSecOps Intelligence Workroom advances toward Signadot-style validation parity and Aurora-style incident investigation parity.

The ledger exists to prevent language drift. A workroom record may be contract-valid without being runtime-valid. A runtime receipt may be verified without certifying full Signadot feature parity.

## Parity classes

### P0 — Contract parity

Meaning: the workroom object model is structurally and semantically checkable.

Required evidence:

- JSON Schema exists for the workroom record;
- canonical semantic validator exists;
- valid pre-merge fixture exists;
- valid post-merge fixture exists;
- valid verified-receipt fixture exists;
- invalid fixture matrix exists and is expected to fail for governance reasons;
- CI runs the validator.

Current status: substantially implemented.

Evidence refs:

- `contracts/workroom/devsecops-workroom-v0.1.schema.json`;
- `tools/validate_devsecops_workroom.py`;
- `tests/fixtures/workroom/devsecops-workroom.pre-merge-validation-failure.valid.json`;
- `tests/fixtures/workroom/devsecops-workroom.pre-merge-verified-receipt.valid.json`;
- `tests/fixtures/workroom/devsecops-workroom.post-merge-incident.valid.json`;
- expected-invalid fixtures under `tests/fixtures/workroom/`;
- `.github/workflows/ci.yml`.

Allowed claim: `contract parity for v0.1 workroom fixtures`.

Forbidden claim: `runtime parity`, `full Signadot parity`, or `production remediation capability`.

### P1 — Runtime receipt parity

Meaning: the workroom can consume verified execution receipt evidence from the owning execution/environment planes.

Required evidence:

- Sociosphere emits or exposes stable environment request/readout references;
- AgentPlane emits or exposes stable runtime run and receipt references;
- Prophet Platform consumes those references without duplicating execution truth;
- a `runtime_receipt` evidence packet has provenance whose `source_ref` matches `source_refs.validation_receipt_ref`;
- `validation_evidence_state: verified_receipt` is present;
- `runtime_parity_level: runtime_observed` is present;
- receipt digest or equivalent integrity reference is present.

Current status: fixture-mode representation exists; cross-plane live handoff still pending.

Allowed claim after evidence: `runtime receipt parity` or `verified receipt consumption`.

Forbidden claim: `full Signadot feature parity`.

### P2 — Signadot-style feature parity

Meaning: the estate has observed evidence for the full Signadot-style sandbox validation capability class.

Required gates:

- PR-scoped environment lifecycle;
- changed-service-only deploy path;
- baseline fallback path;
- HTTP/gRPC route isolation;
- asynchronous queue/topic isolation;
- stateful resource isolation;
- validation job execution evidence;
- teardown and TTL evidence;
- policy, secret, and data-boundary enforcement;
- agent-facing control surface;
- receipt-backed evidence for each gate.

Current status: not certified.

Allowed claim only after all gates have observed evidence: `Signadot-style feature parity`.

Forbidden interim claim: any statement implying full parity from synthetic fixtures, local SVF receipts, or contract-valid workroom records alone.

### P3 — Aurora-style incident investigation parity skeleton

Meaning: the workroom can represent post-merge incidents with evidence-backed investigation, topology/blast-radius context, RCA claims, remediation candidates, and regression fixture candidates.

Required evidence:

- `post_merge_incident` workroom record;
- incident ref;
- investigation run ref;
- topology ref;
- blast-radius ref;
- topology snapshot evidence whose provenance matches the topology ref;
- RCA claims with evidence references;
- remediation plan with action-grant references when risk is high or critical;
- regression fixture candidate derived from the incident.

Current status: fixture-mode representation exists; live connectors and GAIA graph semantics still pending.

Allowed claim: `incident investigation contract skeleton`.

Forbidden claim: `production AIOps autonomous remediation`.

### P4 — Governed DevSecOps Intelligence parity

Meaning: pre-merge validation, post-merge incident investigation, action safety, topology, receipts, and institutional learning operate as a closed loop.

Required evidence:

- P0 contract parity;
- P1 runtime receipt parity;
- P2 Signadot-style feature parity, or explicit scoped subset if incomplete;
- P3 incident investigation skeleton plus live evidence connectors;
- Guardrail/authority fixture coverage for unsafe actions and poisoned evidence;
- GAIA topology/blast-radius semantics;
- Alexandrian Academy postmortem lesson to regression fixture handoff;
- a demonstrated closed loop: incident -> evidence-backed claim -> regression fixture -> validation plan candidate -> future pre-merge gate.

Current status: not certified.

Allowed claim only after evidence: `governed DevSecOps intelligence loop`.

Forbidden interim claim: `self-improving production remediation system`.

## Claim language

Use precise labels:

- `contract_only` — structural/semantic record validity only;
- `synthetic_observed` — synthetic fixture evidence exists;
- `runtime_observed` — verified receipt evidence exists for the scoped validation record;
- `verified_receipt` — receipt-backed evidence state;
- `Signadot-style feature parity` — all P2 gates observed;
- `Aurora-style incident skeleton` — post-merge investigation contract representation only unless live connectors exist.

Do not use these labels loosely:

- `runtime parity` without a scoped qualifier;
- `production-ready`;
- `autonomous remediation`;
- `full parity`;
- `AIOps solved`.

## Current recommended next steps

1. Keep P0 green.
2. Build Prophet Platform adapter from `validate_change` v2 to a workroom record.
3. Bind adapter to Sociosphere and AgentPlane references without duplicating them.
4. Add GAIA topology/blast-radius fixture semantics.
5. Add Guardrail Fabric adversarial fixtures for poisoned evidence and unsafe action posture.
6. Add Alexandrian Academy lesson-to-regression-fixture handoff.

## Non-claims

This ledger does not execute sandbox infrastructure.

This ledger does not certify Signadot-style feature parity.

This ledger does not authorize production remediation.

This ledger does not replace receipt verification by Sociosphere or AgentPlane.
