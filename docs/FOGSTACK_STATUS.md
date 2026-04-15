# Fog Stack status and roadmap

This document captures the current state of Fog Stack work inside `prophet-platform`.

## Repository role

`prophet-platform` is the runtime and deployment substrate for platform services. Fog Stack lands here as the productization, conformance, release, and trust layer for deployable offerings built on that substrate.

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

## Current open review units

As of this capture, the primary open Fog Stack review units are:

- **PR #68** — release artifact backlinking
- **PR #76** — cryptographic signature verification record

These should be treated as the current active trust/release-engineering path.

## Current trust graph shape

The release/trust graph now consists of these machine-readable artifacts:

- release manifest
- validation record
- signature verification record
- signature trust record
- cryptographic signature verification record
- release evidence index

The backlinking tranche under review is what turns those from parallel records into an explicitly linked graph.

## Immediate next tranche

After the current open PRs are accepted, the next release-engineering tranche should focus on:

1. **Cryptographic verification execution** rather than only cryptographic verification record shape.
2. **Automatic backlinking** and deterministic evidence-index production.
3. **CI-emitted verified truth records** instead of shape-only local records.
4. **Signed manifest publication and trust proof** rather than local trust structure only.

## Position in the maturity ladder

Fog Stack in `prophet-platform` is now past initial offering definition. The active frontier is no longer offering taxonomy; it is release/trust hardening.
