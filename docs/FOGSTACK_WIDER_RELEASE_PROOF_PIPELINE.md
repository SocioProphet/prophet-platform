# Fog Stack wider release proof pipeline

This document defines the repo-native **wider release proof pipeline** for Fog Stack.

## Goal

Move from:
- a seal-side proof pipeline
- a separate wider release graph linker

to:
- one wrapper that first executes the seal-side proof pipeline and then links the wider release graph so the main non-seal artifacts carry seal-side proof references.

## Minimal flow

1. provide the manifest, validation record, signature verification record, signature trust record, release seal, bundle identity/version, signature reference, evidence output path, seal crypto record path, and evidence index path
2. invoke `tools/run_fogstack_wider_release_proof_pipeline.py`
3. pass the external verifier command after `--`
4. the wrapper executes the seal proof pipeline and then mutates the wider release graph

## Example

Run the wrapper with the manifest, validation record, signature verification record, signature trust record, release seal, bundle identity, signature reference, output paths, and the external verifier command after `--`.

## What this phase provides

- one orchestrated proof step for the seal side plus the wider release graph
- automatic invocation of the seal proof pipeline
- automatic backlink insertion into the main non-seal release/trust artifacts

## What this phase does not yet provide

- CI enforcement of the wider proof pipeline
- publication of the resulting proof set
- mutation of every downstream consumer of the wider trust graph

Those remain later steps.
