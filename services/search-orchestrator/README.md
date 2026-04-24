# Search Orchestrator Service

This directory is the runtime stub for federated Sherlock search on the platform side.

## Service purpose

The search orchestrator is responsible for accepting Sherlock search requests and returning normalized result objects for workspace/cloud search.

It should eventually:
- accept a Sherlock query object
- query platform workspace indexes
- normalize and return result objects
- preserve permission boundaries and provenance
- expose source markers so higher-level fusion can combine platform results with Lampstand and memory results

## Backing contracts

- `schemas/search/sherlock_search_request.schema.json`
- `schemas/search/sherlock_search_result.schema.json`

## Cross-repo boundaries

- workspace/product semantics live in `SocioProphet/prophet-workspace`
- local desktop indexing remains in `SocioProphet/lampstand`
- memory recall remains in `SocioProphet/memory-mesh`
- ontology/alignment remains in `SocioProphet/ontogenesis`

## First implementation posture

The first implementation should be narrow and inspectable:
- one request shape
- one result shape
- one platform-side execution seam
