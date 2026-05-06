# Semantic Enterprise Import Boundary v0.1

## Purpose

Prophet Platform consumes `semantic-enterprise-v0.1.0` from `SocioProphet/ontogenesis` as a downstream runtime-readable semantic catalog surface.

Ontogenesis remains the authored semantic source of truth. Prophet Platform must not rewrite Ontogenesis semantics at runtime. The platform import boundary exists to preserve source provenance while exposing platform-facing catalog, scenario, query, and named-graph surfaces.

## Source release

- Repository: `SocioProphet/ontogenesis`
- Release/tag: `semantic-enterprise-v0.1.0`
- Manifest: `manifests/semantic_enterprise_v0_1_manifest.json`
- Rollup registry: `catalog/semantic_enterprise_v0_1_registry.ttl`
- Import bridge: `docs/semantic-enterprise/downstream-import-bridge-v0.1.md`

## Platform import contract

The platform-local import fixture is:

- `contracts/semantic-enterprise/v0.1/semantic_enterprise_manifest.import.json`

It defines:

- Ontogenesis source release and source paths
- five sector scenarios
- query paths
- named graph URI fragments
- downstream consumers
- platform output surfaces
- non-goals
- synergetic closure boundary

## Synergetic closure boundary

This import is not just a file copy. It is a membrane between the authored ontology and runtime systems.

The contract distinguishes:

- `inside_source`: Ontogenesis remains the authored semantic source of truth.
- `outside_runtime`: Prophet Platform exposes runtime-readable surfaces without replacing source semantics.
- `boundary_membrane`: provenance, registry references, validation gates, named-graph metadata, trust profile, and access class must survive translation.
- `feedback_surface`: downstream validation and runtime observations become platform evidence, not silent ontology mutation.

## Platform surfaces

The first platform surfaces are named but not yet full services:

- `semantic-enterprise.catalog.v0.1`
- `semantic-enterprise.scenario.v0.1`
- `semantic-enterprise.query.v0.1`
- `semantic-enterprise.named-graph.v0.1`

These names provide the stable contract for follow-on API, catalog, evidence, and search work.

## Validation

Validation entry points:

- `python3 tools/validate_semantic_enterprise_import.py`
- `pytest -q tools/tests/test_semantic_enterprise_import.py`

The pytest smoke tests are included in the existing `test-tools` lane.

## Non-goals

This tranche does not implement production graph storage, live ingestion, operational response playbooks, or access-control enforcement.

Those concerns belong to downstream runtime services and policy systems after the import contract is stable.

## Parent work

- `SocioProphet/prophet-platform#436`
- `SocioProphet/delivery-excellence#21`
