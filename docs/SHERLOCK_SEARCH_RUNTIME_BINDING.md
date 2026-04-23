# Sherlock Search Runtime Binding

This document defines the first runtime binding between the workspace-domain Sherlock search model and the platform runtime.

## Purpose

Sherlock Search is the federated discovery layer above:
- Lampstand local desktop search
- platform/FogGraph workspace search
- memory-mesh recall
- ontogenesis-backed semantic alignment

`prophet-platform` should provide the runtime-facing contracts and service seams that let Sherlock query cloud/workspace indexes and fuse those results with local and memory sources.

## Runtime responsibilities

The platform search runtime should own:
- accepting search requests from workspace surfaces
- delegating cloud/workspace portions of the query to platform indexes
- returning normalized workspace result records
- preserving permission boundaries on every returned object
- providing source metadata so Sherlock can fuse platform results with Lampstand and memory results

## Non-goals

The platform runtime is not the local desktop indexer. That remains Lampstand.

The platform runtime is not the memory runtime. That remains memory-mesh.

The platform runtime is not the ontology authority. Ontogenesis remains the alignment layer.

## First runtime contracts

- `schemas/search/sherlock_search_request.schema.json`
- `schemas/search/sherlock_search_result.schema.json`

## First service seam

A later `services/search-orchestrator/` or equivalent runtime should be able to:
- accept one query object
- query cloud/workspace indexes
- return result objects that Sherlock can rank and fuse with external local/memory sources
