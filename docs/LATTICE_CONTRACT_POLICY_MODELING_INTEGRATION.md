# Lattice Contract, Policy, and Modeling Integration

Lattice surface records are not only search documents. They are contract subjects, policy subjects, and modeling examples.

This companion document extends `docs/LATTICE_SEARCH_GOVERNANCE_INTEGRATION.md` with first-class integration points for:

- `contractforge`
- `policy-fabric`
- `prophet-core-contracts`
- `prophet-core-policy`
- `graphbrain-contract`
- internal metadata classifiers
- internal language-modeling datasets

## Canonical object

The canonical object remains:

```text
PlatformAssetRecord
```

The record identity must not fork per subsystem. Search, policy, contract analysis, and modeling layers may add enrichments, but they must not create a competing asset identity.

## ContractForge integration

ContractForge is the canonical home for contract lifecycle, economic artifact semantics, settlement artifacts, adjustment semantics, and finalization boundaries.

A `PlatformAssetRecord` should map into ContractForge as a contract-referenced asset whenever it affects release rights, runtime eligibility, fleet assignment, obligations, settlement, or governance explanations.

Minimum mapping:

```text
PlatformAssetRecord -> ContractReferencedAsset
assetId -> subject identifier
producerRepo -> source citation
policyRef -> governing policy reference
promotionChannel -> lifecycle state
evidenceCorrelationId -> evidence reference
compatibilitySurfaces -> permitted-use surfaces
```

Required questions:

- Which asset is governed by which contract or policy reference?
- Which project, group, org, device, fleet, or workspace may use it?
- Is the asset candidate, approved, deprecated, revoked, or finalized?
- Which time/effective-state rule applies to a promotion or rollback?
- Which evidence record explains the current state?

## Policy Fabric integration

Policy Fabric is the governed control repository for authoring, validating, packaging, reviewing, replaying, and governing policy-as-code.

A `PlatformAssetRecord` should map into Policy Fabric as a policy subject and evidence carrier.

Minimum mapping:

```text
PlatformAssetRecord -> PolicySubject
assetKind -> policy subject class
policyRef -> PolicyBundle or compiled plan reference
producerRepo -> source repository claim
promotionChannel -> release gate input
evidenceCorrelationId -> validation or replay evidence link
compatibilitySurfaces -> capability constraints
```

Required questions:

- Is this asset allowed to be indexed?
- Is this runtime allowed for this workspace, project, org, or agent?
- Is this boot release allowed for this device or fleet?
- Which validation report justified the state?
- Which replay report can reproduce the decision?

## Contract and language modeling

We need to do data science on our own platform artifacts.

Every `PlatformAssetRecord` should be convertible into examples for contract analysis, policy analysis, search ranking, metadata classification, and language-model evaluation.

Minimum modeling artifacts:

```text
ContractModelExample
PolicyModelExample
SearchIndexDocument
SlashTopicCandidateSet
NewHopeCarrier
GraphbrainArtifactCandidate
```

Minimum modeling fields:

```text
source_record_id
source_kind
plain_language_summary
controlled_vocabulary_terms
slash_topic_candidates
policy_claims
contract_claims
evidence_links
classification_labels
negative_constraints
```

The purpose is to let the platform classify, summarize, test, and explain its own operating artifacts.

## Graphbrain / model-contract integration

Graphbrain-contract treats model and network artifacts as governed objects with architecture probes, patch plans, retrain jobs, and evaluation reports.

Runtime records should connect to this layer when they provide execution context for model training, evaluation, or deployment.

Minimum mapping:

```text
RuntimeAsset -> governed runtime context
PlatformAssetRecord -> model governance subject
compatibilitySurfaces -> execution or evaluation surfaces
policyRef -> training/evaluation constraint
evidenceCorrelationId -> evaluation or release evidence link
```

Required questions:

- Which runtime produced or evaluated a model artifact?
- Which policy constrained the training or evaluation job?
- Which runtime change requires re-evaluation?
- Which evidence links the model result to the runtime state?

## Metadata classifier outputs

The metadata classifier layer must emit enrichment objects, not overwrite canonical records.

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
contract_subject_class
contract_lifecycle_status
policy_subject_class
policy_gate_status
language_modeling_use
```

## Implementation sequence

1. Emit deterministic `PlatformAssetRecordSet` and per-record files.
2. Add deterministic slash-topic candidate sidecars.
3. Add contract/policy/modeling enrichment sidecars.
4. Add Sherlock Search ingestion fixtures.
5. Add Slash Topics topic-pack fixtures.
6. Add New Hope carrier and membrane mapping fixtures.
7. Add ContractForge referenced-asset fixture.
8. Add Policy Fabric policy-subject fixture.
9. Add Graphbrain runtime-context fixture.
10. Persist enriched records through catalog/evidence services.

## Doctrine

Sherlock Search, Slash Topics, New Hope, ContractForge, Policy Fabric, Graphbrain, and Prophet Platform must share one metadata spine.

The platform should understand its own contracts, policies, records, runtimes, and release states well enough to search them, govern them, classify them, train on them, and explain them.
