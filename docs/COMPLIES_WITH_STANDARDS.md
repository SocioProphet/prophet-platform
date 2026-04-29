# Complies with Standards

This repository consumes upstream SocioProphet standards as implementation inputs.

It is the runtime and deployment home where upstream standards become running services, platform contracts, and deployment topology. It is **not** the canonical source of truth for the standards themselves.

## Upstream standards currently relevant here

### Authentication and identity

From `SocioProphet/socioprophet-agent-standards`:

- `docs/standards/authentication/001-agent-authentication-session-and-recovery-standard.md`
- `docs/standards/authentication/002-credential-enrollment-and-authenticator-lifecycle-standard.md`
- `docs/standards/authentication/003-enterprise-federation-and-claim-mapping-standard.md`
- `docs/standards/authentication/004-workload-and-service-identity-standard.md`
- `conformance/CONFORMANCE-CRITERIA-0001.md`

### Other already-pinned standards and references

See `standards.lock.yaml` for the active external standards and reference inputs already pinned by commit.

## Consumption posture

At the time of writing, `prophet-platform` declares the following posture for the auth standards tranche:

- **001** — consumed as the umbrella platform auth/session/recovery posture
- **002** — consumed as the target credential-enrollment and authenticator-lifecycle posture
- **003** — consumed as the target enterprise federation and claim-normalization posture
- **004** — consumed as the target machine/workload identity posture

This declaration is intentionally conservative.

It does **not** claim that every runtime seam in this repository is already fully conformant to the complete upstream standards tranche. It records that these are the standards this repo is aligning to and that future runtime work should be reviewed against them.

## Current binding seams in this repository

The primary seams that should bind to the auth standards tranche are:

- `standards.lock.yaml`
- browser ingress through the gateway
- `contracts/identity/`
- any future or current `apps/identity-prime` runtime lane
- service-to-service identity for platform services

## Current status

Current status should be read as:

- standards-consumption intent is explicit
- runtime alignment is in progress
- broad claims of full conformance are premature until the relevant runtime seams are implemented or updated

## Review rule

Future changes touching auth/session/identity surfaces in this repository should state which upstream standard(s) they implement, extend, or intentionally defer.
