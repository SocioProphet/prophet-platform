# Fog Stack filesystem registry

This document defines the first external-consumable registry adapter for Fog Stack releases.

## Goal

Move from registry-ready CI artifacts to a concrete filesystem registry layout that can be copied, mirrored, served, or adapted into a later network registry.

## Filesystem registry layout

The publisher writes releases under:

- `<registry-root>/<bundle-id>/<version>/registry-publication.index.json`
- `<registry-root>/<bundle-id>/<version>/release-pointer.json`
- `<registry-root>/<bundle-id>/<version>/artifacts/*`

The release pointer includes:

- bundle id
- version
- registry publication index reference
- registry publication index digest

## Minimal flow

1. build a gated registry publication index with `tools/build_fogstack_registry_publication_index.py`
2. check the index with `tools/check_fogstack_registry_publication_index.py`
3. publish it to a filesystem registry with `tools/publish_fogstack_filesystem_registry.py`
4. verify the filesystem registry release with `tools/check_fogstack_filesystem_registry.py`

## What this phase provides

- concrete external-consumable registry layout
- digest-checked artifact copy into the registry
- release pointer for lookup
- CI smoke workflow for publish/check behavior

## What this phase does not yet provide

- authenticated network registry publication
- signed registry root metadata
- rollback or revocation index publication
- registry replication or mirror policy

Those remain later steps.
