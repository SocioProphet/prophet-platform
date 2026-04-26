# Lattice Surface Record Flow

This document explains the first concrete bridge from Fog Stack product surfaces into Prophet Platform.

## Producers

### SourceOS Boot

Repository: `SourceOS-Linux/sourceos-boot`

Primary handoff object:

```text
BootReleaseSet v1
```

Represents boot, live, installer, recovery, rollback, provenance, trust, signature, anti-rollback, telemetry, and evidence-correlation metadata.

### Lattice Forge

Repository: `SocioProphet/lattice-forge`

Primary handoff object:

```text
RuntimeAsset v1
```

Represents runtime class, languages, build metadata, artifacts, provenance, SBOM, signature, scan posture, policy, compatibility surfaces, telemetry, and promotion state.

## Platform ingestion

Prophet Platform owns the ingestion boundary under:

```text
apps/lattice-surface-ingestor/
```

The ingestor is intentionally side-effect-free. It reads one or more handoff objects and emits a normalized record set:

```text
PlatformAssetRecordSet
```

Each entry is a:

```text
PlatformAssetRecord
```

Current normalized asset kinds:

```text
boot-release-set
runtime-asset
```

## Deterministic artifact output

The smoke gate produces a deterministic JSON output artifact:

```text
build/lattice-surface-ingestor/lattice-surface-records.json
```

This artifact is not committed. It is generated during validation and is meant to become the bridge into later catalog/evidence indexing.

## Command

```bash
PYTHONPATH=apps/lattice-surface-ingestor/src \
python3 -m lattice_surface_ingestor.cli ingest \
  contracts/lattice/boot-release-set.v1.example.json \
  contracts/lattice/runtime-asset.v1.example.json \
  --output build/lattice-surface-ingestor/lattice-surface-records.json
```

## Why this matters

The roadmap points toward a community data catalog, AI analytics hub, collaboration, model zoo, reproducible publishing, and knowledge graph. Product-surface records are low-level catalog/evidence primitives. They make boot and runtime artifacts queryable, auditable, and eventually governable through the same catalog and evidence fabric.

## Dependency direction

```text
sourceos-boot      -> BootReleaseSet v1 -> prophet-platform
lattice-forge      -> RuntimeAsset v1   -> prophet-platform
prophet-platform   -> PlatformAssetRecordSet -> catalog/evidence layer
```

`prophet-platform` consumes and normalizes these objects. It does not own boot/recovery implementation or runtime construction.

## Next target

The next platform increment should persist `PlatformAssetRecordSet` into the evidence/catalog service rather than only emitting a build artifact.
