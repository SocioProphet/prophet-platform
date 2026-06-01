# Trust-First Proof Artifacts v0.1

Status: runtime contract draft.

Trust-First proof artifacts are replayable evidence packs for claims over observed Event-IR windows under explicit assumptions. They are not dashboards, alerts, or narrative security claims.

## Core semantics

A proof artifact evaluates a claim over an observed event window. It separates the world from what was observed.

A `PROVED` result means the claim holds for all traces consistent with the observed Event-IR window and declared assumptions. It does not claim exact security of unobserved reality.

A `VIOLATION` result carries a witness or counterexample slice demonstrating a forbidden state or transition.

An `INCONCLUSIVE` result means the system does not know: evidence is missing, assumptions are too weak, precision is insufficient, or budgets prevented certification.

## Artifact contract

Schema: `schemas/proof-artifact.schema.json`

Required fields include schema version, artifact id, claim kind/params, assumptions, policy bundle hash/signature, compiler id, domains, budgets, inputs hash, result, and precision.

## Event-IR contract

Schema: `schemas/event-ir.schema.json`

Each event is typed and scoped. If an event cannot be typed, scoped, or authenticated, it cannot justify a `PROVED` artifact.

Core fields:

- `id`
- `kind`
- `ts`
- `actor`
- `scope`
- `target`
- `attrs`
- `auth`

## Claim kinds

Initial claim kinds:

- `boundary_non_escape`
- `ifc_no_flow`
- `capability_confinement`
- `usage_budget`
- `kms_key_usage`

## Coverage contracts

The checker must enforce minimum coverage by claim kind. For `kms_key_usage`, required event families include:

- `Policy.Pin`
- `KMS.Decrypt`
- `Token.Consume`
- `Data.Write`
- `Net.Send`
- `Identity.Attest`

Missing required evidence blocks `PROVED` and should produce or preserve `INCONCLUSIVE`.

## Trust roots

Trust roots are part of the artifact, not an external story.

- Event authenticity: events are attributable to a signed or attested source.
- Scope authenticity: scopes are attested or supplied by a trusted boundary oracle.
- Policy authenticity: policy bundle is hash-pinned and signed.
- Clock model: event order and skew are explicitly declared.
- Checker identity: checker version and behavior are pinned.

## Domains and budgets

The artifact records abstract domains and budgets so precision and cost are visible. Budget exhaustion must not be disguised as proof.

Supported domain labels in v0.1:

- `intervals`
- `signs`
- `octagon`
- `polyhedra`
- `nnc_polyhedra`
- `congruence`
- `sharing`
- `labels`
- `capabilities`

## Relationship to boundaries

Proof artifacts are boundary surfaces. Their sufficiency is scoped:

- A proof artifact may be `audit_sufficient` for a declared claim.
- It is not automatically `microstate_sufficient`.
- It does not prove safety outside its observation window and assumptions.

Sociosphere records artifact availability in the Boundary Atlas. Policy Fabric decides whether a proof artifact is admissible for claim-mode promotion.
