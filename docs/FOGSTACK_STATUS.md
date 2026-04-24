# Fog Stack status and roadmap

This document captures the current state of Fog Stack work inside `prophet-platform`.

## Repository role

`prophet-platform` is the runtime and deployment substrate for platform services. Fog Stack lands here as the productization, conformance, release, and trust layer for deployable offerings built on that substrate.

## Repository strategy decision

Fog Stack should **not** split into separate repositories for AI, Data, Automation, Security, or other future pack categories yet.

At the current stage, the trust/release machinery is still highly shared across all surfaces. Splitting now would mostly increase coordination overhead and fragment the release/trust graph before those categories have clearly independent lifecycles.

The correct near-term move is:
- keep the engineering and trust/release machinery in `prophet-platform`
- track future pack categories here as product surfaces and readiness states
- split into separate repos only when a pack has an independently justified lifecycle, release cadence, operator surface, and support burden

See also:
- `docs/FOGSTACK_PACKS.md`
- `catalog/fogstack-packs-v0.1.yaml`

## Merged offering slices

The following initial offering slices are already merged into `main`:

- **Fog Stack Access** — initial upstream offering slice via PR #25
- **Fog Stack Knowledge** — governed ingress + local daemon offering slice via PR #26
- **Fog Stack Evaluation** — evaluation fabric offering slice via PR #27

## Merged validation and release-engineering slices

The following supporting slices are already merged into `main`:

- native validator/helper surfaces and initial Access bundle/rulepack
- release metadata refresh via PR #41
- release schemas and validation execution criteria via PR #42
- CI-oriented validation-record emitter via PR #48
- native `Makefile` validation hook refresh via PR #51
- signed-manifest attachment helper via PR #52
- signed-manifest verification helper via PR #58
- signature trust evidence record via PR #62
- release evidence index via PR #63
- artifact backlinking via PR #68
- cryptographic signature verification record via PR #76
- external signature verification input normalization via PR #93

## Current open review units

As of this capture, the primary open Fog Stack review units are:

- **PR #119** — external signature verification runner
- **PR #121** — release sealing
- **PR #123** — release seal signature support

These should be treated as the current active trust/release-engineering path.

## Product-pack readiness matrix

The detailed matrix and pack taxonomy now live in:
- `docs/FOGSTACK_PACKS.md`
- `catalog/fogstack-packs-v0.1.yaml`

## Current trust graph shape

The release/trust graph now consists of these machine-readable artifacts:

- release manifest
- validation record
- signature verification record
- signature trust record
- cryptographic signature verification record
- release evidence index
- release seal

The open trust/release PRs are what move this system from linked artifacts to a more cryptographically grounded, tamper-evident release graph.

## Immediate next tranche

After the current open PRs are accepted, the next release-engineering tranche should focus on:

1. **Verification execution** rather than only verification record shape.
2. **Seal signing and seal-signature trust** rather than unsigned seal computation only.
3. **CI-emitted verified truth records** instead of shape-only or local records.
4. **Automatic artifact/backlink mutation** so the graph becomes self-updating under the release pipeline.

## Position in the maturity ladder

Fog Stack in `prophet-platform` is now past initial offering definition. The active frontier is no longer offering taxonomy; it is release/trust hardening and future pack-boundary justification.
