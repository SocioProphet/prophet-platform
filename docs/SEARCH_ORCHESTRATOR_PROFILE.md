# Sherlock Search Orchestrator Runtime Profile

This document defines the first platform runtime profile for federated Sherlock search.

## Purpose

The search orchestrator is the runtime layer that accepts a Sherlock query and fans out to the relevant backends:
- local desktop search signals from Lampstand
- workspace/cloud search signals from platform indexes
- memory recall signals from memory-mesh
- semantic normalization signals from ontogenesis-aligned units and entities

## Platform responsibility

`prophet-platform` should own the runtime-facing orchestration seam for workspace/cloud search and result normalization.
It should not replace Lampstand or memory-mesh; it should consume their outputs through stable contracts.

## First runtime contracts

- `schemas/search/sherlock_search_request.schema.json`
- `schemas/search/sherlock_search_result.schema.json`

## First service seam

A later `services/search-orchestrator/` service should:
- accept one Sherlock request
- query platform/FogGraph indexes
- return normalized search results
- preserve permission boundaries and provenance signals
- expose source markers so higher-level fusion can combine platform results with Lampstand and memory results

## Non-goals

- desktop crawling and indexing
- memory storage and recall policy
- ontology authoring

Those remain in `lampstand`, `memory-mesh`, and `ontogenesis`.
