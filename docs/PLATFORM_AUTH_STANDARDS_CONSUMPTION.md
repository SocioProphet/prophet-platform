# Platform Authentication Standards Consumption Plan

## Purpose

This document records how `prophet-platform` should consume the merged SocioProphet agent authentication standards without overreaching into unrelated runtime work.

It is intentionally an **alignment and gap-declaration document**, not a claim that the platform has already fully implemented the complete authentication stack.

## Upstream standards consumed

`prophet-platform` should consume the following upstream standards from `SocioProphet/socioprophet-agent-standards`:

- `docs/standards/authentication/001-agent-authentication-session-and-recovery-standard.md`
- `docs/standards/authentication/002-credential-enrollment-and-authenticator-lifecycle-standard.md`
- `docs/standards/authentication/003-enterprise-federation-and-claim-mapping-standard.md`
- `docs/standards/authentication/004-workload-and-service-identity-standard.md`
- `conformance/CONFORMANCE-CRITERIA-0001.md`

## Why this repo is the first consumer

The repository README already states that standards and governance stay in dedicated upstream repositories and that `prophet-platform` is where those standards become running services, deployment topologies, and platform contracts.

That makes `prophet-platform` the correct first implementation-side consumer for the auth standards tranche.

## Current platform seams relevant to auth

From the current repository posture, the most relevant seams are:

- `standards.lock.yaml`
  - already pins upstream standards and reference inputs
  - already includes identity-facing generated artifact targets such as `contracts/identity/`
  - already names `apps/identity-prime` as a runtime target under the standards-consumption model
- `docs/ARCHITECTURE.md`
  - documents browser ingress via a small HTTP gateway that relays internally over TriTRPC
- browser shell / portal surfaces
- gateway ingress surfaces
- future `identity-prime` runtime lane
- identity and evidence contract directories

## Current gap statement

At the time of writing:

1. The platform has an upstream standards-consumption mechanism (`standards.lock.yaml`), but it does **not yet explicitly pin or declare consumption of the auth standards tranche** from `socioprophet-agent-standards`.
2. The architecture document exposes browser ingress and internal transport posture, but it does **not yet describe a first-class browser auth/session architecture** in the same explicit way.
3. The standards lock references identity-oriented generated artifacts and an `apps/identity-prime` runtime target, but the implementation posture for that lane is still under-specified from the repository’s public-facing docs.

## Intended implementation posture

The platform should align to the upstream auth standards with the following shape:

### Browser lane

- browser ingress remains through the gateway
- browser auth/session posture should align to the upstream standard’s first-party session and gateway/BFF expectations
- browser runtime code should not introduce ad hoc long-lived front-end token storage

### Enterprise federation lane

- tenant routing and external proof should align to the enterprise federation standard
- any enterprise IdP claim handling should be normalized before authorization decisions
- external proof should still terminate in platform-controlled first-party session/state

### Identity runtime lane

- `apps/identity-prime` should become the explicit runtime landing zone for identity and session orchestration in the platform
- `contracts/identity/` should carry the generated/platform contracts needed by that runtime lane
- implementation should remain additive and not silently reshape unrelated services

### Workload/service identity lane

- machine identities for platform services should align to the workload/service identity standard
- service-to-service auth should not reuse human/browser auth posture
- runtime targets consuming downstream APIs should use audience-scoped machine credentials

## Safe next implementation steps

The next safe implementation steps in this repo are:

1. add an explicit standards-consumption declaration for the auth standards tranche in `standards.lock.yaml`
2. add a "Complies with Standards" reference from the README or another canonical repo entry point
3. add or refine the `identity-prime` runtime lane documentation before touching broader runtime auth behavior
4. only after those steps, make narrow runtime changes tied to one explicit auth seam at a time

## Things this document does **not** claim

This document does **not** claim that:

- the full passkey/browser/session architecture is already implemented in this repo
- enterprise federation is already fully realized here
- the machine identity lane is already complete
- the gateway or browser surfaces are already fully conformant to the upstream auth standards

It is a disciplined statement of **where the standards should bind** and **what the next safe move is**.

## Recommended follow-on PR order

1. standards-lock auth import / pin update
2. README or canonical entrypoint compliance declaration
3. identity-prime runtime lane documentation
4. narrow implementation PRs for specific auth/session seams
