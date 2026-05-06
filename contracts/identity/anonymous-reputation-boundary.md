# Anonymous Reputation Boundary

## Purpose

This note records how the platform-facing anonymous reputation contracts relate to the identity contract lane.

The current anonymous reputation contracts live at the top level of `contracts/` because they were introduced as runtime/materialization contracts for Alexandrian constitutional-floor work:

- `contracts/AnonymousReputationReceipt.v0.1.json`
- `contracts/LinkabilityScope.v0.1.json`
- `contracts/RevocationToken.v0.1.json`
- `contracts/TraceOpenRequest.v0.1.json`

They are identity-adjacent, but they are not replacements for identity proof, subject normalization, or session state.

## Boundary rule

Anonymous reputation contracts must consume or reference normalized identity/seam outputs; they must not become a parallel identity system.

The expected ordering is:

1. `IdentityProofIngressRecord` records proof ingress result.
2. `IdentitySubjectContext` normalizes subject, tenant, assurance, and policy context.
3. `LinkabilityScope` defines a bounded scope where repeated pseudonymous actions may be publicly or auditor-linkable.
4. `AnonymousReputationReceipt` records a scoped reputation event under a pseudonymous subject commitment.
5. `RevocationToken` and `TraceOpenRequest` provide bounded accountability paths when policy permits.

## Non-goals

This note does not implement cryptography, authentication, revocation, trace-open, or session behavior. It prevents contract drift while those runtime seams are designed.

## Follow-on

A later PR may move these schemas under `contracts/identity/anonymous-reputation/` after runtime consumption and validation paths are stable.
