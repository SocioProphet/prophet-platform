# Lattice Search, Topic, and Governance Integration

Lattice surface records must not stop at platform-local evidence files. They are discovery, classification, governance, and data-science inputs.

This document fixes the integration seam that must exist between:

- `prophet-platform`
- `sherlock-search`
- `slash-topics`
- `new-hope`
- later catalog/evidence services

## Why this exists

The failure mode to avoid is the classic suite-integration failure: search, studio, discovery, governance, and model tooling each develop their own metadata model. That makes language models, cataloging, discovery, and governance feel bolted together rather than native.

For Prophet Lattice, every product-surface record must be:

1. searchable by Sherlock Search;
2. scoped and classified by Slash Topics;
3. available to New Hope-style semantic/runtime governance;
4. preserved as evidence for catalog, model, runtime, and boot provenance.

## Current producer

`apps/lattice-surface-ingestor` emits:

```text
PlatformAssetRecordSet
```

and can persist deterministic per-asset files:

```text
build/lattice-surface-ingestor/store/*.json
```

## Sherlock Search integration contract

Sherlock Search is the canonical Sherlock-related search/discovery repo.

The handoff from Prophet Platform to Sherlock should use each `PlatformAssetRecord` as an indexable document.

Minimum index fields:

```text
assetId
assetKind
name
version
sourceKind
sourceApiVersion
producerRepo
policyRef
evidenceCorrelationId
promotionChannel
compatibilitySurfaces
```

Recommended Sherlock document envelope:

```json
{
  "docType": "lattice.platformAssetRecord",
  "assetId": "runtime-asset:prophet-python-ml:0.1.0",
  "title": "prophet-python-ml 0.1.0",
  "body": "RuntimeAsset v1 from SocioProphet/lattice-forge",
  "metadata": {
    "assetKind": "runtime-asset",
    "producerRepo": "SocioProphet/lattice-forge",
    "promotionChannel": "dev",
    "compatibilitySurfaces": ["jupyter", "ray", "beam", "agentplane", "sourceos-user", "prophet-platform"]
  }
}
```

Sherlock must be able to search and facet over boot/runtime records alongside content, research, project, model, and dataset records.

## Slash Topics integration contract

Slash Topics are governed, signed, replayable scopes for search and knowledge surfaces.

Every `PlatformAssetRecord` should receive deterministic topic candidates from metadata alone before any ML classifier runs.

Minimum generated slash topics:

```text
/lattice
/lattice/runtime
/lattice/boot
/sourceos
/fogstack
/governance
/evidence
/provenance
```

Mapping rules:

```text
assetKind=boot-release-set -> /lattice/boot /sourceos /recovery /release
assetKind=runtime-asset -> /lattice/runtime /forge /notebook /agentplane
producerRepo=SourceOS-Linux/sourceos-boot -> /sourceos /boot /recovery
producerRepo=SocioProphet/lattice-forge -> /forge /runtime /supply-chain
promotionChannel=dev -> /lifecycle/dev
```

Slash Topics should later provide signed topic-pack outputs for these records so Sherlock and New Hope consume the same scope vocabulary.

## New Hope integration contract

New Hope is the higher-order semantic runtime for agentic commons, with first-class concepts such as carrier, receptor, membrane, runtime, Message, Thread, Claim, Citation, Entity, Lens, and ModerationEvent.

For Lattice surface records, New Hope should consume the records as semantic carriers for governance and classification.

Minimum New Hope mapping:

```text
PlatformAssetRecord -> Carrier
assetId -> Entity.id
producerRepo -> Citation.source
policyRef -> Claim.policyRef
evidenceCorrelationId -> Evidence/Citation link
compatibilitySurfaces -> Lens candidates
promotionChannel -> Lifecycle/Governance attribute
```

The membrane model should answer:

- Is this asset allowed to be discoverable?
- Is this runtime allowed for this project/user/org?
- Is this boot release approved for this device/fleet?
- Which metadata classifiers have touched the record?
- Which evidence objects justify its governance state?

## Metadata classifier requirements

The metadata classifier layer must treat platform asset records as first-class objects.

Required classifier outputs:

```text
asset_class
lifecycle_stage
risk_class
surface_scope
producer_domain
supply_chain_posture
evidence_completeness
search_visibility
slash_topic_candidates
new_hope_membrane_status
```

These classifier outputs should be appended to the record as a downstream enrichment object, not overwrite the canonical producer record.

## Non-duplication rule

Do not create separate Sherlock-only, Slash-only, or New-Hope-only schemas for boot/runtime assets.

The canonical object is:

```text
PlatformAssetRecord
```

Search, topic, and governance layers may add enrichments, but the platform record remains the source of truth for asset identity.

## Near-term implementation sequence

1. `prophet-platform`: emit deterministic `PlatformAssetRecordSet` and per-record files.
2. `prophet-platform`: add deterministic topic candidate generation sidecar.
3. `sherlock-search`: add ingestion fixture for `PlatformAssetRecord` documents.
4. `slash-topics`: add topic-pack fixture for Lattice/FogStack asset records.
5. `new-hope`: add Carrier/Lens/Membrane mapping fixture for `PlatformAssetRecord`.
6. `prophet-platform`: persist enriched records through catalog/evidence service.

## Doctrine

Search, studio, catalog, governance, and model/runtime management must share the same metadata spine.

Sherlock Search is not a sidecar. Slash Topics are not decoration. New Hope is not post-hoc moderation. They are the discovery, scoping, and semantic governance layers for the same Lattice asset graph.
