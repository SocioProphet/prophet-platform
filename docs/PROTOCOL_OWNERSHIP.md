# Protocol ownership

`prophet-platform` is the shipping platform and deployment hub.

It is **not** the canonical source of truth for TritRPC framing, fixture vectors, or transport semantics.

## Canonical split

- `TriTRPC` owns:
  - protocol framing
  - fixture vectors
  - deterministic encoding rules
  - transport/compliance hardening notes
  - reference implementations and parity tests
- `prophet-platform` owns:
  - deployable apps
  - gateway integration
  - UDS wiring and platform topology
  - portal and infrastructure integration

## Rule

When platform docs need to describe transport or framing, they should link to `TriTRPC` rather than restating the normative behavior locally.

## Why this file exists

This note is here to prevent split-brain protocol ownership between the platform repo and the protocol repo.
