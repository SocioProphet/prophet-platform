# identity-prime Contract Consumption

## Purpose

This note records how the `identity-prime` runtime lane should consume the first identity contracts now present under `contracts/identity/`.

This is a documentation-only step. It does not implement authentication, session storage, federation, recovery, or machine identity behavior.

## Contracts consumed

- `contracts/identity/IdentityProofIngressRecord.v0.1.json`
  - ingress record for accepted, rejected, or inconclusive identity proof
- `contracts/identity/IdentitySubjectContext.v0.1.json`
  - normalized internal subject, tenant, and assurance context
- `contracts/identity/IdentitySessionContext.v0.1.json`
  - first-party platform session context shape

## Intended flow

The first runtime seam should be:

1. receive a proof ingress result from an approved upstream lane
2. emit or persist an `IdentityProofIngressRecord`
3. normalize that proof into an `IdentitySubjectContext`
4. later, after session behavior is explicitly implemented, issue an `IdentitySessionContext`

## Review rules

Future implementation PRs should state:

- which identity contract they consume or emit
- which upstream auth standard they satisfy
- which behavior is intentionally deferred
- whether the PR changes subject, tenant, assurance, or session semantics

## Non-goals

This note does not claim that `identity-prime` currently implements the above flow. It only defines the expected contract consumption order for future narrow runtime PRs.
