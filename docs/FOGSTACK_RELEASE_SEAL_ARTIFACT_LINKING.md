# Fog Stack release seal artifact linking

This document defines the first repo-native backlinking step for release seal artifacts.

## Goal

Move from separate release seal artifacts to artifacts that explicitly point to each other:
- the release seal
- the release seal cryptographic verification record
- the release evidence index

## Minimal flow

1. emit the release seal
2. emit the release seal cryptographic verification record
3. emit or prepare the release evidence index
4. run `tools/link_fogstack_release_seal_artifacts.py`

## Example

Run the linker with the seal file, the seal crypto-verification record file, and the evidence index file.

## What this phase provides

- `release_evidence_index_ref` on the seal
- `release_seal_cryptographic_verification_record_ref` on the seal
- `release_seal_ref` and `release_seal_cryptographic_verification_record_ref` on the evidence index

## What this phase does not yet provide

- CI automation of backlink insertion
- cryptographic verification of linked refs
- publication of the linked artifact set

Those remain later steps.
