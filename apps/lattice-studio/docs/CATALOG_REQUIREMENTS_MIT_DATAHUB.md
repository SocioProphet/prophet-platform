# Lattice Studio Catalog Requirements from MIT DataHub

This note captures requirements from the MIT CSAIL DataHub lineage for the Lattice Studio / catalog vertical slice.

## Source project

MIT CSAIL DataHub was described by the MIT Database Group as an experimental hosted platform, GitHub-like, for organizing, managing, sharing, collaborating on, and making sense of data.

The useful product frame:

```text
manage data -> use others' data -> make sense of data
```

Functional areas to learn from:

```text
ingestion
curation
sharing
collaboration
discovery
linking
query
analytics
visualization
machine learning
versioned datasets
```

## Requirement for Prophet Lattice

Lattice Studio must not be only a notebook launcher.

It must become a governed collaborative data-science workbench where notebook sessions are linked to catalog assets, runtime assets, evidence, policies, and search/topic/governance enrichments.

## Minimum Lattice Studio / Catalog vertical slice

The first demo-grade slice must include:

1. Project workspace.
2. Runtime selection from `RuntimeAsset`.
3. NotebookSession record.
4. Catalog input binding.
5. Evidence output.
6. Search/discovery indexing through `PlatformAssetRecord`.
7. Topic classification through Slash Topics.
8. Semantic governance through New Hope.
9. Policy/contract context through Policy Fabric and ContractForge.
10. A path to query/analytics/visualization rather than just static metadata.

## Catalog object implications

A catalog asset should have:

```text
asset id
owner
version
schema or shape
source reference
license/usage policy
curation state
quality state
lineage/evidence
linked notebook sessions
linked runtime assets
search document
topic candidates
policy/contract subject mapping
```

## NotebookSession implications

A notebook session should record:

```text
project id
user id
runtime asset id
kernel name
catalog inputs
policy reference
created time
session digest
evidence reports
```

This is why `NotebookSession` is the first Lattice Studio object in this tranche.

## Design rule

Do not repeat the IBM failure pattern where Studio, Discovery, catalog, language/modeling, and governance each own separate metadata identities.

Lattice Studio must use the same metadata spine as the rest of Prophet Lattice:

```text
RuntimeAsset / BootReleaseSet
  -> PlatformAssetRecord
  -> enrichments
  -> search/topics/governance/policy/contract/modeling
  -> catalog/workbench experience
```

## Next implementation targets

1. Add `CatalogAsset` and `CatalogAssetVersion` fixtures in `prophet-platform`.
2. Bind `NotebookSession.catalogInputs[]` to real `CatalogAsset` identifiers.
3. Emit a `NotebookSessionEvidence` record for each session.
4. Convert notebook/session/catalog records into `PlatformAssetRecord` objects.
5. Feed those records into Sherlock Search and Slash Topics.
6. Add a small analytics/visualization stub so the demo shows data use, not only metadata.
