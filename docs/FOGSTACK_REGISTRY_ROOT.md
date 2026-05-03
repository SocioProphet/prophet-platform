# Fog Stack registry root and rollback index

This document defines the repo-native registry root metadata and rollback/revocation index for Fog Stack releases.

## Goal

Move from a filesystem registry layout to a root metadata surface that records the current registry state and a rollback/revocation index that can mark releases as revoked or rolled back.

## Registry root metadata

The registry root metadata schema lives at:

- `schemas/release/fogstack-registry-root-metadata-v0.1.schema.json`

The registry root records:

- registry URI
- release entries
- release pointer references and digests
- registry publication index references and digests
- rollback/revocation index reference and digest
- signature metadata for future signed-root enforcement

## Rollback / revocation index

The rollback/revocation index schema lives at:

- `schemas/release/fogstack-registry-revocation-index-v0.1.schema.json`

The index records release entries with:

- bundle id
- version
- status: `revoked` or `rollback`
- reason
- optional superseding release reference

## Minimal flow

1. publish one or more releases into the filesystem registry
2. build a rollback/revocation index with `tools/build_fogstack_registry_revocation_index.py`
3. check it with `tools/check_fogstack_registry_revocation_index.py`
4. build registry root metadata with `tools/build_fogstack_registry_root_metadata.py`
5. check it with `tools/check_fogstack_registry_root_metadata.py`

## What this phase provides

- registry root metadata schema
- rollback/revocation index schema
- builders and checkers for both surfaces
- CI coverage for root and rollback/revocation behavior

## What this phase does not yet provide

- cryptographic signing and verification of registry root metadata
- externally hosted registry root publication
- automated client-side rollback enforcement
- KMS/HSM-backed registry root signing keys

Those remain later hardening steps.
