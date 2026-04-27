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
- link runtime use to NotebookSession, NotebookSurfacePlane, AgentAsset, ModelAsset, PipelineAsset, and EvidenceBundle objects.

### Lattice Studio notebook surfaces

Consumer repo: `SocioProphet/prophet-platform`

Platform object: `NotebookSurfacePlane v1`

Design rule:

- Lattice Studio must not hard-code Jupyter as the notebook ontology.
- Notebook surfaces are adapter-based and bind to `RuntimeAsset.spec.compatibility.surfaces`.
- RuntimeAsset fixtures must retain `jupyter` as a legacy compatibility alias while advertising concrete adapter surfaces.

Required notebook/workbench adapter surfaces:

```text
jupyter
jupyterlab
zeppelin
observable
plutojl
quarto
lattice-studio
```

Adapter responsibilities:

- `jupyterlab`: default scientific notebook adapter.
- `zeppelin`: collaborative analytics, Spark, SQL, Scala, Python, and R workflows.
- `observable`: browser-native reactive visualization and data storytelling.
- `plutojl`: Julia/reactive scientific computing workflows.
- `quarto`: reproducible technical publishing, dashboards, books, slides, and notebook-derived reports.
- `lattice-studio`: governed workbench surface binding RuntimeAsset, NotebookSession, catalog inputs, policies, and evidence.

## Validation contract

`make validate` now includes `lattice-surfaces-check`, implemented by:

```text
tools/validate_lattice_surfaces.py
```

The check validates platform-facing example payloads under:

```text
contracts/lattice/
```

Lattice Studio tests also guard adapter drift by requiring RuntimeAsset fixtures to cover every active NotebookSurfacePlane adapter.

## Dependency direction

The platform consumes product-surface contracts. It does not own the implementation details of boot/recovery or runtime construction.

- `sourceos-boot` owns boot/recovery implementation.
- `lattice-forge` owns runtime construction and evidence sidecars.
- `prophet-platform` owns platform ingestion, assignment, policy binding, notebook surface orchestration, session records, and evidence correlation.
- `sourceos-spec` should become the canonical home for stable shared schemas once these contracts harden.

## Doctrine

Lattice is the control plane. SourceOS is the substrate. Fog is where execution happens.
