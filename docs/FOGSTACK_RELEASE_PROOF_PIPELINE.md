# Fog Stack release proof pipeline

This document defines the first repo-native **release proof pipeline** for the seal side of Fog Stack.

## Goal

Move from separate helpers for:
- external release seal verification execution
- release seal cryptographic verification record emission
- release seal artifact backlinking

to:
- one wrapper that runs the external seal verifier, emits the seal cryptographic verification record, and then links the resulting artifacts into the seal-side trust graph.

## Minimal flow

1. provide the release seal, bundle identity/version, signature reference, and evidence index
2. invoke `tools/run_fogstack_release_proof_pipeline.py`
3. pass the external verifier command after `--`
4. the wrapper emits the seal cryptographic verification record and updates the seal-side backlinks

## Example

Use the wrapper with a seal file, a signature reference, output paths for evidence and the cryptographic verification record, an evidence index path, and the external verifier command after `--`.

## What this phase provides

- one orchestrated proof step for the seal side of the trust graph
- automatic invocation of the seal verification wrapper
- automatic backlink insertion after the cryptographic record is produced

## What this phase does not yet provide

- CI enforcement of the proof pipeline
- mutation of the non-seal side of the wider trust graph
- registry publication of the resulting proof set

Those remain later steps.
