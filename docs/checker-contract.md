# Proof Artifact Checker Contract v0.1

Status: runtime verifier draft.

The checker is the small trusted verifier for Trust-First proof artifacts. The certifier may be expensive and complex. The checker must be deterministic, auditable, and conservative.

## Inputs

- Proof artifact conforming to `schemas/proof-artifact.schema.json`
- Event-IR window conforming to `schemas/event-ir.schema.json`
- Policy bundle identified by artifact `policy_bundle.hash`
- Canonicalization rules for event window and config
- Approved checker configuration

## Required checker behavior

### 1. Schema validation

The checker validates:

- artifact schema version is allowlisted;
- artifact required fields are present;
- Event-IR events validate against the approved Event-IR schema;
- unknown schema versions are rejected.

### 2. Policy bundle validation

The checker validates:

- `policy_bundle.hash` matches the supplied policy bundle;
- `policy_bundle.sig` is valid when signature enforcement is enabled;
- `compiler_id` is allowlisted for the claim kind.

### 3. Input hash validation

The checker recomputes:

```text
inputs_hash = sha256(canonical_events || canonical_config)
```

If the recomputed hash differs from the artifact `inputs_hash`, the artifact is rejected.

### 4. Coverage gate

The checker evaluates claim-kind coverage requirements. For `kms_key_usage`, `PROVED` requires at minimum:

- `Policy.Pin`
- `Identity.Attest`
- `Token.Consume`
- `KMS.Decrypt`
- `Data.Write`
- `Net.Send`

If a required family is missing, `PROVED` is invalid and the result must be rejected or downgraded to `INCONCLUSIVE` by the caller.

### 5. Verdict-specific checks

#### PROVED

The checker must reject `PROVED` when:

- required coverage is absent;
- event integrity is weaker than the allowed profile;
- scope integrity is weaker than the allowed profile;
- budgets were exhausted;
- precision metadata indicates cutoff or unsound approximation;
- input hash mismatch occurs.

#### VIOLATION

The checker validates that the witness/counterexample slice:

- references event IDs present in the Event-IR window;
- is consistent with event ordering and scope assumptions;
- reaches or demonstrates the forbidden state or transition claimed.

#### INCONCLUSIVE

The checker validates that uncertainty is explicit:

- missing evidence;
- weak integrity;
- weak scope binding;
- budget exhaustion;
- precision loss;
- unknown clock/order model.

`INCONCLUSIVE` is a valid artifact result. It is not proof of safety.

## Canonicalization guidance

Canonicalization must be deterministic:

- JSON keys sorted;
- stable event ordering by event ID or declared log order;
- no implicit defaults not recorded in the artifact;
- exact config included in hash calculation;
- schema and compiler versions pinned.

## Policy handoff

The checker returns a validation result. Policy Fabric decides whether the checked artifact permits a boundary crossing or claim-mode promotion.

Recommended policy defaults:

- `PROVED` + approved assumptions may permit promotion to the artifact's supported claim mode.
- `VIOLATION` blocks promotion and routes counterexample metadata.
- `INCONCLUSIVE` blocks promotion and creates an evidence-gap backlog item.

## Non-goals

The checker does not:

- decide all security properties exactly;
- prove claims outside the observed window and assumptions;
- replace runtime hardening;
- treat logs or dashboards as proof by themselves;
- silently repair missing evidence.
