# SourceOS M2 filesystem registry

This document defines the current local filesystem-registry proof path for the SourceOS M2 lifecycle bundle.

## Goal

Move from a generated deterministic M2 lifecycle proof bundle to a concrete local registry layout that can later be served, mirrored, or consumed by a boot/recovery planner.

## Inputs

The registry publisher consumes the proof bundle emitted by:

```bash
python tools/build_sourceos_m2_lifecycle_proof.py --output-dir <proof-dir>
```

That bundle contains:

- `config-source.json`
- `release-set.json`
- `boot-release-set.json`
- `nlboot-crosswalk.json`
- `fingerprint.json`
- `compliance-result.json`
- `proof-index.json`

## Registry layout

The publisher writes:

- `<registry-root>/sourceos/<release-id>/<version>/release-pointer.json`
- `<registry-root>/sourceos/<release-id>/<version>/proof-index.json`
- `<registry-root>/sourceos/<release-id>/<version>/artifacts/*`

The release pointer records:

- release id
- version
- proof index digest
- copied proof artifacts and digests

## Safety boundary

This remains a local proof artifact publication path.

It does not add:

- network registry publication
- artifact fetching by boot clients
- host mutation
- disk writes
- `kexec`
- remote state mutation

## Validation

The SourceOS contracts workflow now runs:

```bash
python tools/smoke_sourceos_m2_filesystem_registry.py
```

That smoke builds the M2 lifecycle proof bundle, publishes it into a temporary filesystem registry, and verifies that the release pointer references the required proof artifacts.

## Follow-on

Next useful tranche:

1. make nlboot consume a registry-published manifest fixture without side effects,
2. emit a synthetic boot `Fingerprint`, and
3. validate that synthetic boot `Fingerprint` against the assigned `ReleaseSet` and `BootReleaseSet`.
