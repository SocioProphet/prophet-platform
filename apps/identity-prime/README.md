# identity-prime

`identity-prime` is the intended platform runtime lane for identity normalization and first-party session shaping inside `prophet-platform`.

This directory is currently a **placeholder runtime landing zone**.

It exists so future implementation work has a clear, bounded home and does not drift into unrelated gateway or service surfaces.

## Why this lane exists

The upstream SocioProphet agent standards define the platform posture for:

- authentication, session, and recovery
- credential enrollment and authenticator lifecycle
- enterprise federation and claim mapping
- workload and service identity

`prophet-platform` is the runtime and deployment hub where those upstream standards become platform behavior.

`identity-prime` is the intended runtime seam for that work.

## Intended responsibilities

This lane is expected to cover:

- first-party session orchestration
- normalization of external identity proof into internal subject / tenant / assurance context
- platform-facing identity contracts
- identity/session lifecycle evidence emission

## Current status

This subtree does **not** yet claim a full implementation.

At this stage it is a designated runtime landing zone and boundary marker.

## Review rule

Future PRs that touch this lane should state:

- which upstream auth standard(s) they implement
- which ingress or session seam they bind
- what they intentionally defer

## Related platform seams

- `standards.lock.yaml`
- `contracts/identity/`
- gateway/browser ingress
- enterprise identity ingress
- service-to-service identity handoff
