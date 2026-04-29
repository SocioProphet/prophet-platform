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

The registry lifecycle builder writes:

- `<registry-root>/rollback-revocation.index.json`

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
- signature metadata, either `shape-only` or `openssl-rsa-sha256`

The rollback/revocation index includes:

- rollback target release pointers and digests
- revocation or suspension entries for release pointers
- lifecycle index digest over canonical JSON
- signature metadata, either `shape-only` or `openssl-rsa-sha256`

## Minimal flow

1. build a gated registry publication index with `tools/build_fogstack_registry_publication_index.py`
2. check the index with `tools/check_fogstack_registry_publication_index.py`
3. publish it to a filesystem registry with `tools/publish_fogstack_filesystem_registry.py`
4. verify the filesystem registry release with `tools/check_fogstack_filesystem_registry.py`
5. build registry-root metadata with `tools/build_fogstack_filesystem_registry_root.py`
6. check registry-root metadata with `tools/check_fogstack_filesystem_registry_root.py`
7. build rollback/revocation lifecycle metadata with `tools/build_fogstack_registry_rollback_revocation_index.py`
8. check rollback/revocation lifecycle metadata with `tools/check_fogstack_registry_rollback_revocation_index.py`
9. verify registry metadata signatures with `tools/run_openssl_fogstack_registry_metadata_verifier.py`

## Registry root semantics

The registry root is the consumer-facing catalog root for a filesystem registry export. It does not replace per-release pointer checks. Instead, it lets consumers verify that the exported registry root consistently names the release pointers and publication indexes available in the registry.

## Rollback and revocation semantics

The rollback/revocation index records release lifecycle state outside the immutable release pointer itself.

Rollback targets are releases that operators may return to. A rollback target may be `eligible`, `preferred`, or `deprecated`.

Revocations are releases that consumers should not select. A revocation may be `revoked` or `suspended` and must carry a reason.

A release must not be both a rollback target and a revocation entry in the same lifecycle index. The checker enforces that conflict rule and validates pointer digests against the filesystem registry.

## Registry metadata signature verification

`tools/run_openssl_fogstack_registry_metadata_verifier.py` verifies detached OpenSSL RSA/SHA-256 signatures over canonicalized registry metadata.

The canonical payload is the metadata JSON with `signatures` set to an empty array and encoded with sorted keys and compact separators. This makes verification stable across formatting changes while keeping the signature metadata out of the signed payload.

This local verification tranche supports:

- `FogStackFilesystemRegistryRoot`
- `FogStackRegistryRollbackRevocationIndex`
- `openssl-rsa-sha256` signature entries
- tamper rejection for modified metadata

## What this phase provides

- concrete external-consumable registry layout
- digest-checked artifact copy into the registry
- release pointer for lookup
- registry-root metadata covering release pointers and publication indexes
- rollback/revocation lifecycle metadata for registry consumers
- local OpenSSL verification for registry metadata signatures
- dedicated CI workflows for registry-root, registry-lifecycle, and registry metadata signature behavior

## What this phase does not yet provide

- authenticated network registry publication
- KMS/HSM-backed production signing keys
- registry replication or mirror policy
- policy-engine selection of rollback targets

Those remain later steps.
