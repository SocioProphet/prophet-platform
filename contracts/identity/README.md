# Identity Contracts

This directory contains platform-facing identity contract placeholders aligned to the locked `agent-auth-standards` import in `standards.lock.yaml`.

These contracts are intentionally small v0.1 schema surfaces. They establish the first shared vocabulary for identity normalization and session shaping without claiming a complete runtime implementation.

## Current contracts

- `IdentitySubjectContext.v0.1.json`
  - internal subject, tenant, and assurance context after identity proof normalization
- `IdentitySessionContext.v0.1.json`
  - first-party session context shape for platform consumers
- `IdentityProofIngressRecord.v0.1.json`
  - record of accepted, rejected, or inconclusive identity proof ingress

## Upstream standards

These contracts should be reviewed against:

- `SocioProphet/socioprophet-agent-standards` authentication standard 001
- credential lifecycle standard 002
- enterprise federation and claim mapping standard 003
- workload and service identity standard 004
- conformance criteria 0001

## Non-goals

This directory does not implement authentication, session storage, passkey UX, enterprise federation, or machine identity issuance.

Runtime behavior should land separately under the `apps/identity-prime` lane or a specific platform ingress seam.
