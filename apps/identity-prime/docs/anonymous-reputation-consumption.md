# identity-prime Anonymous Reputation Consumption

## Purpose

This note binds the already-merged anonymous reputation contracts to the `identity-prime` contract-consumption lane without claiming a runtime implementation.

The intent is to keep scoped anonymous reputation subordinate to the identity proof and subject-normalization path.

## Inputs

The anonymous reputation lane should consume:

- `contracts/identity/IdentityProofIngressRecord.v0.1.json`
- `contracts/identity/IdentitySubjectContext.v0.1.json`
- `contracts/identity/IdentitySessionContext.v0.1.json` when session semantics are implemented

## Runtime-adjacent contracts

The following top-level contracts are currently consumed as constitutional-floor runtime contracts:

- `contracts/LinkabilityScope.v0.1.json`
- `contracts/AnonymousReputationReceipt.v0.1.json`
- `contracts/RevocationToken.v0.1.json`
- `contracts/TraceOpenRequest.v0.1.json`

## Intended flow

1. Receive an accepted or inconclusive identity proof ingress result.
2. Normalize subject context and assurance level.
3. Resolve whether a constitutional or guild scope permits pseudonymous participation.
4. Select or create a `LinkabilityScope` for that bounded scope.
5. Emit an `AnonymousReputationReceipt` for qualifying scoped activity.
6. Only emit `RevocationToken` or `TraceOpenRequest` under a declared authority path and trigger policy.

## Runtime constraints

- Anonymous reputation must not create identity.
- Anonymous reputation must not weaken assurance requirements.
- Linkability must be scoped.
- Trace-open must be authority-bound and policy-referenced.
- Revocation must be recorded as a policy-governed event, not an informal operator action.

## Non-goals

This note does not implement anonymous credentials, zero-knowledge proofs, revocation registries, trace-open execution, or session behavior. It documents the intended consumption boundary for future narrow runtime PRs.
