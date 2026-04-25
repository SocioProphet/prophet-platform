# Fog Stack wider release graph

This document defines the next widening step for the Fog Stack trust graph.

## Goal

Move from a seal-side trust graph to a wider release graph where the primary non-seal artifacts also carry references to the release seal and the release-seal cryptographic verification record.

## Minimal flow

1. produce or update the manifest, validation record, signature verification record, and signature trust record
2. produce the release seal and the release-seal cryptographic verification record
3. run `tools/link_fogstack_wider_release_graph.py`

## Example

Run the linker with:
- the manifest
- the validation record
- the signature verification record
- the signature trust record
- the release seal
- the release-seal cryptographic verification record

## What this phase provides

- `release_seal_ref` on the main release/trust artifacts
- `release_seal_cryptographic_verification_record_ref` on the main release/trust artifacts

## What this phase does not yet provide

- CI automation of wider-graph mutation
- cryptographic verification of the linked refs themselves
- publication of the wider linked graph

Those remain later steps.
