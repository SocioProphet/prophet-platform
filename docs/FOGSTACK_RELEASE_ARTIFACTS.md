# Fog Stack release artifacts (initial metadata phase)

This document defines the first machine-readable release surfaces for Fog Stack offerings already merged into `prophet-platform`.

## Artifacts in this phase

- `catalog/fogstack-support-states-v0.1.yaml`
- `releases/fogstack.access-v0.1.release.json`
- `releases/fogstack.knowledge-v0.1.release.json`
- `releases/fogstack.evaluation-v0.1.release.json`

## Purpose

These files are the smallest upstream step beyond prose release policy:
- support-state metadata becomes machine-readable
- each merged offering gets a release-manifest stub
- publication can later evolve without redesigning bundle identity

## What is not solved yet

This phase does not yet include:
- signed bundle manifests
- publication endpoints or registry integration
- evidence package emission
- automatic support-state publication

Those belong to the next release-engineering tranche.
