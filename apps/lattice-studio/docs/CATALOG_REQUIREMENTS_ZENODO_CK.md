# Lattice Studio Catalog Requirements from Zenodo and CK/CMX

This note captures requirements from Zenodo and Collective Knowledge / Collective Mind / CMX for the Lattice Studio and catalog vertical slice.

## Zenodo requirements

Zenodo's core repository unit is a record composed of metadata, files, and a persistent identifier. Published files and persistent identifiers are immutable. Updates create new versions. Zenodo also has a concept DOI for all versions and a version DOI for each specific version.

Lattice implications:

1. `CatalogAsset` must distinguish a durable asset concept from immutable asset versions.
2. `CatalogAssetVersion` must be immutable after publication.
3. File/object digests must be recorded before promotion.
4. Metadata may be amended, but file payload identity must not be silently rewritten.
5. Every published catalog asset should be capable of carrying an external persistent identifier field.
6. Access policy must support public metadata with restricted file access.
7. Version-specific citation and concept-level citation must both be representable.

Minimum fields:

```text
catalogAssetId
conceptPersistentId
versionPersistentId
version
metadata
files
fileDigests
accessPolicy
creators
publicationDate
relatedWorks
license
communitiesOrCollections
```

## CK / Collective Knowledge / CMX requirements

CK and its successor lineage around Collective Mind / CMX focus on FAIR, reusable, portable artifacts and automations across code, data, models, scripts, experiments, software, hardware, and workflows.

Lattice implications:

1. Catalog assets must be file-based and portable where possible.
2. Artifacts need extensible JSON/YAML metadata.
3. Reusable automations must be first-class catalog objects, not hidden scripts.
4. Workflows should be chainable across models, datasets, software, and hardware.
5. Notebook sessions should record workflow/action metadata for rerun and reuse.
6. Runtime, hardware, dataset, model, and script inputs should all be represented as linked assets.
7. Reproducibility evidence should be generated as part of the normal workbench path.

Minimum fields:

```text
automationId
action
inputs
outputs
runtimeAssetId
hardwareProfile
softwareProfile
datasetRefs
modelRefs
scriptRefs
workflowRefs
reproduceCommand
```

## Combined Lattice requirement

Lattice Studio must combine three ideas:

```text
MIT DataHub: collaborative data workbench and catalog
Zenodo: durable archival records, persistent IDs, immutable versions
CK/CMX: portable reusable artifacts and automations with FAIR metadata
```

Therefore a notebook session is not enough. The demo vertical slice must evolve toward:

```text
CatalogAsset -> CatalogAssetVersion -> RuntimeAsset -> NotebookSession -> Evidence -> Search/Topics/Governance
```

## Immediate implementation sequence

1. Add `NotebookSession` and `NotebookSessionEvidence`.
2. Add `CatalogAsset` and `CatalogAssetVersion` fixtures.
3. Bind notebook `catalogInputs[]` to catalog asset versions.
4. Add a reproducibility command / workflow action field to notebook evidence.
5. Add citation/persistent identifier fields to catalog versions.
6. Convert catalog and notebook objects into `PlatformAssetRecord` and enrichment sidecars.
7. Make Sherlock Search index catalog/notebook/session records.

## Design rule

A dataset, runtime, notebook, automation, model, or evidence artifact is not first-class unless it is:

```text
findable
versioned
citable or referenceable
policy-governed
reproducible
linked to runtime and evidence
searchable
classified by topics
governable by semantic membranes
```
