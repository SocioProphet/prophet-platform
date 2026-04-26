# Prophet Lattice Product Surfaces

Prophet Platform is the runtime and deployment hub for Prophet Lattice. This document records how the first Fog Stack product surfaces enter the platform contract layer.

## Surfaces covered in this tranche

### Fog Boot / SourceOS Boot

Producer repo: `SourceOS-Linux/sourceos-boot`

Platform handoff object: `BootReleaseSet v1`

Platform responsibility:

- ingest BootReleaseSet metadata;
- assign BootReleaseSets to device, project, group, or organization scopes;
- require evidence correlation IDs;
- bind boot/recovery actions to PolicyBundle and ReleaseSet state;
- collect boot evidence into the platform evidence lane.

### Lattice Forge

Producer repo: `SocioProphet/lattice-forge`

Platform handoff object: `RuntimeAsset v1`

Platform responsibility:

- ingest RuntimeAsset metadata;
- expose approved runtimes to projects, deployment spaces, notebooks, agents, and shell sessions;
- require provenance, SBOM, signature, scan, compatibility, telemetry, and promotion fields;
- link runtime use to NotebookSession, AgentAsset, ModelAsset, PipelineAsset, and EvidenceBundle objects.

## Validation contract

`make validate` now includes `lattice-surfaces-check`, implemented by:

```text
tools/validate_lattice_surfaces.py
```

The check validates platform-facing example payloads under:

```text
contracts/lattice/
```

## Dependency direction

The platform consumes product-surface contracts. It does not own the implementation details of boot/recovery or runtime construction.

- `sourceos-boot` owns boot/recovery implementation.
- `lattice-forge` owns runtime construction and evidence sidecars.
- `prophet-platform` owns platform ingestion, assignment, policy binding, and evidence correlation.
- `sourceos-spec` should become the canonical home for stable shared schemas once these contracts harden.

## Doctrine

Lattice is the control plane. SourceOS is the substrate. Fog is where execution happens.
