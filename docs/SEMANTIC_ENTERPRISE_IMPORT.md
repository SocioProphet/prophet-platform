# Semantic Enterprise Import Boundary v0.1

Prophet Platform consumes `semantic-enterprise-v0.1.0` from `SocioProphet/ontogenesis` as a platform-readable semantic catalog surface.

Ontogenesis remains the authored semantic source of truth. Prophet Platform exposes platform-facing catalog, scenario, query, and named-graph surfaces while preserving provenance back to the source release.

## Source release

- Repository: `SocioProphet/ontogenesis`
- Release/tag: `semantic-enterprise-v0.1.0`
- Manifest: `manifests/semantic_enterprise_v0_1_manifest.json`
- Rollup registry: `catalog/semantic_enterprise_v0_1_registry.ttl`

## Platform import contract

- `contracts/semantic-enterprise/v0.1/semantic_enterprise_manifest.import.json`

The import contract records source paths, five sector scenarios, query paths, named graph URI fragments, downstream consumers, platform output surfaces, and the closure boundary between authored source and platform runtime.

## Closure boundary

The import contract distinguishes:

- `inside_source`: authored source remains in Ontogenesis.
- `outside_runtime`: Prophet Platform publishes platform-readable surfaces.
- `boundary_membrane`: provenance and governance metadata survive translation.
- `feedback_surface`: downstream observations are recorded as platform evidence.

## Validation

- `python3 tools/validate_semantic_enterprise_import.py`
- `pytest -q tools/tests/test_semantic_enterprise_import.py`

The pytest smoke tests are covered by the existing `test-tools` lane.

## Parent work

- `SocioProphet/prophet-platform#436`
- `SocioProphet/delivery-excellence#21`
