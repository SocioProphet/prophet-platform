# Fog Stack filesystem registry

This document defines the first external-consumable registry adapter for Fog Stack releases.

## Goal

Move from registry-ready CI artifacts to a concrete filesystem registry layout that can be copied, mirrored, served, or adapted into a later network registry.

## Filesystem registry layout

The publisher writes releases under:

- `<registry-root>/<bundle-id>/<version>/registry-publication.index.json`
- `<registry-root>/<bundle-id>/<version>/release-pointer.json`
- `<registry-root>/<bundle-id>/<version>/artifacts/*`

The registry-root builder writes:

- `<registry-root>/registry-root.json`

The release pointer includes:

- bundle id
- version
- registry publication index reference
- registry publication index digest

The registry root includes:

- registry URI
- generated timestamp
- release pointer references and digests
- registry publication index references and digests
- a root digest computed over canonical JSON
- signature metadata in shape-only form for this tranche

## Minimal flow

1. build a gated registry publication index with `tools/build_fogstack_registry_publication_index.py`
2. check the index with `tools/check_fogstack_registry_publication_index.py`
3. publish it to a filesystem registry with `tools/publish_fogstack_filesystem_registry.py`
4. verify the filesystem registry release with `tools/check_fogstack_filesystem_registry.py`
5. build registry-root metadata with `tools/build_fogstack_filesystem_registry_root.py`
6. check registry-root metadata with `tools/check_fogstack_filesystem_registry_root.py`

## Registry root semantics

The registry root is the consumer-facing catalog root for a filesystem registry export. It does not replace per-release pointer checks. Instead, it lets consumers verify that the exported registry root consistently names the release pointers and publication indexes available in the registry.

This tranche uses shape-only signature metadata. It establishes the object and checker path without claiming KMS/HSM-backed registry-root signing.

## What this phase provides

- concrete external-consumable registry layout
- digest-checked artifact copy into the registry
- release pointer for lookup
- registry-root metadata covering release pointers and publication indexes
- CI smoke workflow for publish/check/root behavior

## What this phase does not yet provide

- authenticated network registry publication
- cryptographic registry-root signature verification
- rollback or revocation index publication
- registry replication or mirror policy

Those remain later steps.
