# Office Cloud Suite Runtime

## Purpose

This document defines the platform runtime split for the SourceOS office and workspace suite.

`prophet-platform` is the runtime and deployment home for the cloud office control plane. It should realize the office suite product semantics defined in `SocioProphet/prophet-workspace` and the host integration surfaces defined in `SociOS-Linux/source-os`.

## Runtime responsibilities

The platform should own:
- WOPI host behavior and document session control
- document metadata, versions, locks, and writeback records
- office preview and conversion workers
- office context extraction and indexing runtime
- AI action routing and receipt emission
- workflow runtime for office/document automations
- deployment topology, namespaces, and service wiring
- memory-backed recall and writeback hooks for office/document actions
- cloud search and retrieval surfaces that can consume local-search and workspace-index signals

## Service set

Planned service surfaces:
- `services/wopi-host/`
- `services/office-render-convert/`
- `services/office-context-extractor/`
- `services/workspace-ai-orchestrator/`
- `services/office-action-service/`
- `services/workspace-agent-studio/`
- adapter bindings to `memory-mesh`
- search/runtime bindings that can consume `lampstand`-derived desktop discovery where appropriate

## Cross-repo integration

### Upstream product/domain

`SocioProphet/prophet-workspace` should define:
- workspace office capability families
- product parity expectations
- user-facing and admin-facing semantics
- where memory-backed recall and desktop/cloud search appear in the workspace UX

### Downstream host realization

`SociOS-Linux/source-os` should define:
- LibreOffice defaults
- local extraction hooks
- local smoke tests
- font and MIME integration
- desktop office shell behavior
- Lampstand desktop indexing/search handoff
- local memory-mesh hooks where allowed by policy

### Shared runtime dependencies

`SocioProphet/memory-mesh` should act as the canonical memory runtime for:
- recall-before-action
- writeback-after-action
- user and project continuity for office workflows
- memory-backed agent flows for drafting, summarization, and task creation

`SocioProphet/lampstand` should act as the canonical desktop indexing/search runtime for:
- local office file discovery
- inspectable local indexing health and stats
- search handoff from SourceOS desktop into workspace office surfaces

## First runtime contracts

The first runtime contracts should include:
- office document record
- office AI action record
- office AI receipt record
- workspace flow record

Those contracts should support local desktop and cloud editing paths without binding the product to a single editor implementation.

## Editor posture

The runtime should treat LibreOffice / Collabora as an editing and conversion engine, not as the total product. The workspace graph, AI orchestration, memory hooks, and document-control services belong at the platform layer.
