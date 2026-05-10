# Trust-First Proof Artifacts v0.1

Status: contract bootstrap.

Trust-First proof artifacts turn platform/runtime/security claims into replayable evidence packets. A proof artifact is not a dashboard and not a narrative. It is a structured object that pins the claim, assumptions, input hash, policy bundle, compiler/checker identity, abstract domains, budgets, precision, and verdict.

## Verdicts

### PROVED

`PROVED` means: for all traces consistent with the observed Event-IR window and declared assumptions, the claim invariant holds.

It does not mean the unknowable real world is safe outside coverage. It means the claim is established over `Consistent(L, A)` where `L` is the observed Event-IR and `A` is the artifact assumption set.

### VIOLATION

`VIOLATION` means: the artifact contains a concrete counterexample or witness slice consistent with the observed event window that reaches a forbidden state or transition.

The slice should be minimal enough for incident response and audit routing.

### INCONCLUSIVE

`INCONCLUSIVE` means: the system cannot prove or refute the claim under the current evidence, trust roots, precision, or budgets.

This is valid evidence of uncertainty. It must not be promoted to a safety claim.

## Required artifact structure

The canonical schema is `schemas/proof-artifact.schema.json`.

Required fields:

- `schema_version`
- `artifact_id`
- `claim.kind`
- `claim.params`
- `assumptions.coverage`
- `assumptions.event_integrity`
- `assumptions.scope_integrity`
- `assumptions.clock_model`
- `assumptions.missing_evidence`
- `policy_bundle.hash`
- `policy_bundle.sig`
- `compiler_id`
- `domains`
- `budgets`
- `inputs_hash`
- `result`
- `precision`

## Claim kinds

Initial claim kinds:

- `boundary_non_escape`
- `ifc_no_flow`
- `capability_confinement`
- `usage_budget`
- `kms_key_usage`

## Assumption discipline

Every artifact must declare its assumptions. The checker and Policy Fabric should reject or downgrade claims whose assumptions are not allowlisted for the intended claim mode.

Minimum assumptions:

- coverage: event families captured and trusted;
- event integrity: append-only/signature/Merkle/best-effort/fixture;
- scope integrity: how scope metadata is bound;
- clock model: monotonic/wall/skew/reorder assumptions;
- missing evidence: explicit evidence gaps.

## Input hash discipline

`inputs_hash` binds the artifact to:

- canonical Event-IR window;
- claim params;
- policy bundle hash;
- compiler id;
- domain config;
- budgets and widen schedule.

An input hash mismatch means the artifact is not about the supplied input window.

## Domain and precision discipline

The `domains` field records the abstract domains used: intervals, octagons, polyhedra, congruence, sharing, labels, or capabilities.

The `precision` object records whether the result is exact or approximate and includes a scalar `delta` for summary dashboards. The structured proof object remains authoritative; `delta` is a summary.

Budget exhaustion or unreported precision loss must block `PROVED`.

## Relation to boundary atlas

Sociosphere records proof artifacts as evidence contracts. Policy Fabric consumes the artifact verdict to decide claim-mode promotion or boundary-crossing admissibility.

The platform emits evidence; Policy Fabric decides admission; Sociosphere records jurisdiction and coverage.

## Non-goals

This contract does not implement the abstract interpreter. It defines the artifact/checker boundary first so implementations can vary while the evidence shape remains stable.
