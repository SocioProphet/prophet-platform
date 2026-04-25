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

## Canonical upstream refs

The proof pipeline can now also stamp the release evidence index with optional canonical upstream refs so the release-proof artifact set points back to the already-merged Fog ownership surfaces.

Supported optional refs:
- `--canonical-contract-surface-ref`
- `--canonical-deployment-surface-ref`
- `--canonical-runtime-surface-ref`
- `--canonical-policy-surface-ref`

Recommended targets are the live upstream homes:
- `SocioProphet/api-spec` under `fog/`
- `SocioProphet/manifests` under `fog/`
- `SocioProphet/cloudshell-fog`
- `SocioProphet/policy-fabric`

## Example

Use the wrapper with a seal file, a signature reference, output paths for evidence and the cryptographic verification record, an evidence index path, the optional canonical upstream refs, and the external verifier command after `--`.

## What this phase provides

- one orchestrated proof step for the seal side of the trust graph
- automatic invocation of the seal verification wrapper
- automatic backlink insertion after the cryptographic record is produced
- optional insertion of canonical upstream refs into the release evidence index so the proof set names the shared Fog contract, deployment, runtime, and policy surfaces it depends on

## What this phase does not yet provide

- CI enforcement of canonical upstream refs
- mutation of the non-seal side of the wider trust graph
- registry publication of the resulting proof set

Those remain later steps.
