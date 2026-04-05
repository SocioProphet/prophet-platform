# Storage Integration Blueprint

This document lands the first bounded multi-store storage architecture for Prophet Platform.

We use multiple stores **on purpose**, but we do **not** allow them to become multi-master peers for the same fact classes.

## Canonical ownership

- **Dolt** owns branchable tabular operational state.
  - Observation
  - RunRecord
  - ProjectionManifest
  - PromotionRejection
- **TypeDB** owns semantic truth.
  - Entity
  - Claim
  - ProvenanceLink
  - Capability
  - PolicyBinding
- **Neo4j** is a read-optimized projection for operator traversal and graph UX.
- **RDF/SPARQL** stores are optional standards-interchange projections.
- **TerminusDB** is optional and bounded to collaborative linked-document bundles if it later proves its value.

## Demonstration scope

The first platform demonstration should prove:

1. an Observation lands in Dolt-oriented operational contracts;
2. a promotion run converts it into TypeDB-oriented semantic contracts;
3. a ProjectionManifest records the derived graph projection;
4. a Neo4j-shaped read model can be materialized without becoming canonical truth.

## Object classes

### Operational / Dolt-owned

- `Observation`
- `RunRecord`
- `ProjectionManifest`
- `PromotionRejection`

### Semantic / TypeDB-owned

- `Entity`
- `Claim`
- `ProvenanceLink`
- `Capability`
- `PolicyBinding`

## Promotion rule

Promotion from Observation to Claim must be deterministic and replayable.

Inputs:
- input observations
- ontology reference
- mapping reference
- validator references
- target schema version

Outputs:
- created/reused entities
- created claims
- provenance links
- rejection rows
- projection manifests for any derived read models

## Field ownership rule

A field belongs in TypeDB if it expresses semantic identity, semantic relations, admissibility state, provenance semantics, capability semantics, or policy-bearing meaning.

A field belongs in Dolt if it expresses batch/run bookkeeping, branch state, operational timestamps, import/export bookkeeping, validation bookkeeping, or projection bookkeeping.

A field belongs in projection stores only if it is reproducible from canonical sources.

## Repo landing

- `docs/` holds architectural rationale and operating guidance.
- `schemas/contracts/` holds canonical object contracts.
- `schemas/examples/` holds worked example manifests and sample payloads.
- Future runtime services may land under `apps/` once contract shapes are accepted.

## MVP order

1. Land contracts and examples.
2. Land one demonstrator flow.
3. Add Neo4j projection shape.
4. Defer RDF and TerminusDB until the core path is stable.
