# Fog Stack registry publication

This document defines the first repo-native registry-ready publication surface for Fog Stack.

## Goal

Move from gated promotion artifacts in CI to a registry publication index that can be consumed by a future registry or distribution plane.

## Registry publication index

The registry publication index schema lives at:
- `schemas/release/fogstack-registry-publication-index-v0.1.schema.json`

The index records:
- registry URI
- promoted manifest publication set reference and digest
- release publication gate record reference and digest
- artifact references and digests

## Minimal flow

1. build or collect a promoted manifest publication set
2. require a passing release publication gate record
3. run `tools/build_fogstack_registry_publication_index.py`
4. check the resulting index with `tools/check_fogstack_registry_publication_index.py`
5. upload or publish the index and referenced artifacts

## Current CI boundary

The current workflow emits a registry-ready artifact set as a GitHub Actions artifact. It does not yet publish to an external registry.

The workflow uses a synthetic passing publication gate record for the registry-index smoke path. The stricter promotion workflow is responsible for producing real policy, approval, signature, and gate artifacts. A future tranche should compose those workflow outputs directly rather than reconstructing a gate fixture.

## What this phase provides

- typed registry publication index
- builder and checker helpers
- CI artifact publication for the registry-ready set
- digest checks for all indexed artifacts

## What this phase does not yet provide

- external registry publication
- promotion workflow artifact handoff into the registry workflow
- registry authentication or publication credentials
- revocation or rollback index publication

Those remain later steps.
