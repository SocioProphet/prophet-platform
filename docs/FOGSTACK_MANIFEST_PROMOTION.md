# Fog Stack manifest promotion

This document defines the repo-native **manifest promotion** path for Fog Stack.

## Goal

Move from:
- a canonical manifest publication set

to:
- a promoted manifest set that carries target channel and support-state values appropriate for the next release lane.

## Minimal flow

1. build the canonical publication set with `tools/build_fogstack_manifest_publication_set.py`
2. run `tools/promote_fogstack_manifest_publication_set.py`
3. provide the support-state catalog and optional target channel/support-state overrides
4. persist the resulting promoted manifest set as a publishable artifact

## Example

Run the promotion helper with:
- an input publication-set directory
- an output directory
- `catalog/fogstack-support-states-v0.1.yaml`
- optional `--target-channel` and `--target-support-state` overrides

## What this phase provides

- channel/support-state mutation for the publishable manifest set
- promotion metadata in the output publication-set index
- lifecycle-status carry-through from the support-state catalog

## What this phase does not yet provide

- signed publication backed by external signing infrastructure by default
- registry publication of the promoted manifest set
- policy-gated promotion approval logic

Those remain later steps.
