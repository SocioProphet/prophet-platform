# Lattice Cross-Repo Integration Ledger

This ledger records the current `PlatformAssetRecord` integration spine across Prophet Platform and related SocioProphet repositories.

## Canonical identity

The canonical platform asset identity is:

```text
PlatformAssetRecord
```

Produced by:

```text
SocioProphet/prophet-platform
apps/lattice-surface-ingestor
```

Primary generated artifacts:

```text
build/lattice-surface-ingestor/lattice-surface-records.json
build/lattice-surface-ingestor/lattice-surface-enrichments.json
build/lattice-surface-ingestor/store/manifest.json
```

## Producer product surfaces

| Producer repo | Handoff object | Platform record kind | Role |
|---|---|---|---|
| `SourceOS-Linux/sourceos-boot` | `BootReleaseSet v1` | `boot-release-set` | Boot, live, installer, recovery, rollback, trust, telemetry, boot evidence |
| `SocioProphet/lattice-forge` | `RuntimeAsset v1` | `runtime-asset` | Runtimes, kernels, SBOMs, provenance, scans, promotion, runtime evidence |

## Downstream integration consumers

| Consumer repo | Fixture / contract | Purpose | Status |
|---|---|---|---|
| `SocioProphet/sherlock-search` | `contracts/lattice/platform-asset-index-document.v1.schema.json` | Sherlock Search index envelope for Lattice asset records | merged |
| `SocioProphet/slash-topics` | `protocols/lattice/platform-asset-topic-pack.v1.json` | Governed slash-topic candidates for platform assets | merged |
| `SocioProphet/new-hope` | `fixtures/lattice/platform-asset-carrier.v1.json` | New Hope Carrier/Membrane mapping for platform assets | merged |
| `SocioProphet/contractforge` | `examples/lattice/platform-asset-contract-reference.v1.json` | Contract-referenced asset fixture | merged |
| `SocioProphet/policy-fabric` | `examples/lattice/platform-asset-policy-subject.v1.json` | Policy subject fixture and gate context | merged |
| `SocioProphet/graphbrain-contract` | `examples/lattice/platform-runtime-context.v1.json` | Runtime/model governance context | merged |

## Search and discovery path

```text
PlatformAssetRecord
  -> PlatformAssetRecordEnrichment.search
  -> sherlock-search PlatformAssetIndexDocument
  -> searchable/facet-able discovery document
```

Sherlock Search must index boot/runtime assets alongside content, data, model, project, policy, contract, and governance records. This prevents a Watson Discovery / Watson Studio style split where search and studio metadata diverge.

## Topic and membrane path

```text
PlatformAssetRecord
  -> PlatformAssetRecordEnrichment.slashTopics
  -> slash-topics SlashTopicPack
  -> new-hope CarrierFixture / membrane questions
```

Slash Topics define shared scope vocabulary. New Hope consumes the same identity as a semantic carrier with membrane questions and evidence requirements.

## Contract and policy path

```text
PlatformAssetRecord
  -> PlatformAssetRecordEnrichment.contractForge
  -> ContractReferencedAssetFixture

PlatformAssetRecord
  -> PlatformAssetRecordEnrichment.policyFabric
  -> PolicySubjectFixture
```

ContractForge handles contract lifecycle, permitted-use surfaces, lifecycle state, effective-state questions, and explanation contexts.

Policy Fabric handles policy subjects, validation/replay evidence, promotion gates, runtime eligibility, boot-release eligibility, and exception handling.

## Model governance path

```text
RuntimeAsset
  -> PlatformAssetRecord(runtime-asset)
  -> Graphbrain RuntimeGovernanceContextFixture
  -> NetworkArtifact / ArchitectureProbe / RetrainJob / ModelEvaluationReport loop
```

Graphbrain-contract ties runtime state to model training, evaluation, retraining, architecture probing, and promotion decisions.

## Non-duplication invariant

No downstream repository should create a competing asset identity for the same boot or runtime asset.

Allowed:

```text
enrichment sidecars
fixtures
index envelopes
topic packs
carrier mappings
policy subjects
contract references
model governance contexts
```

Forbidden:

```text
separate IDs that replace PlatformAssetRecord.assetId
repo-local canonical identities for the same asset
unlinked search-only or policy-only copies
```

## Next integration targets

1. Add a `sherlock-search` ingestion command or fixture converter that reads `PlatformAssetRecordEnrichmentSet`.
2. Add a `slash-topics` replay fixture proving the topic pack output is deterministic.
3. Add a `new-hope` membrane replay fixture against the Lattice carrier.
4. Add a `contractforge` explanation fixture for runtime approval / rollback state.
5. Add a `policy-fabric` validation/replay report fixture for the runtime policy subject.
6. Add a `prophet-platform` catalog/evidence persistence service that stores both canonical records and enrichments.
7. Add `sociosphere` topology registration so these repo dependencies are enforced.

## Doctrine

The metadata spine is part of the product. Search, studio, catalog, governance, contracts, policy, and model runtime management must share it.

If a boot/runtime asset cannot be searched, scoped, governed, reasoned over contractually, evaluated as policy, and linked to model/runtime evidence, it is not yet first-class in Prophet Lattice.
