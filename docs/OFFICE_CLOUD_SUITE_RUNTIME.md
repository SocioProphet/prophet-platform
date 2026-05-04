# Office Cloud Suite Runtime

## Purpose

This document defines the platform runtime split for the SourceOS office and workspace suite.

`prophet-platform` is the runtime and deployment home for the open cloud-office control plane. It realizes the office-suite product semantics defined in `SocioProphet/prophet-workspace` and binds them to the current SourceOS host/user surfaces under `SourceOS-Linux/*`.

This is not a Microsoft 365 or Google Workspace dependency layer. SourceOS must provide parity with those suites while keeping the canonical product, runtime authority, storage contracts, policy decisions, and evidence records open, inspectable, and self-hostable.

## Runtime responsibilities

The platform owns:

- WOPI host behavior and document session control
- document metadata, versions, locks, writeback records, and conflict state
- office preview and conversion workers
- asynchronous office context extraction and indexing runtime
- AI action routing and receipt emission
- workflow runtime for office/document automations
- deployment topology, namespaces, service wiring, and health/smoke surfaces
- permission-aware collaboration runtime for comments, review threads, suggestions, and review-state transitions

The WOPI hot path must remain narrow and inspectable. Extraction, indexing, semantic graph updates, memory attachment, and AI follow-ons happen after version capture or through explicit policy-approved actions; they do not sit inside the critical editor save path.

## Six-lane split

The office suite is a six-lane system, not a standalone office clone.

| Lane | Repository surface | Ownership boundary |
|---|---|---|
| Product/domain | `SocioProphet/prophet-workspace` | Workroom semantics, office capability families, user/admin product expectations, OfficeArtifact contracts, review expectations, and workroom binding. |
| Platform runtime | `SocioProphet/prophet-platform` | WOPI, records, locks, writeback, conversion, context extraction, AI receipts, workflow runtime, service wiring, and deployment topology. |
| Local execution | `SourceOS-Linux/sourceos-devtools` and Agent Machine contracts | Guarded local generation, inspection, conversion, evidence emission, scoped output roots, and dry-run-by-default CLI behavior. |
| Shell/document surface | `SourceOS-Linux/sourceos-shell` | Linux-first document/PDF/native shell behavior, local/cloud handoff affordances, secure document lanes, and desktop integration. |
| Operator terminal surface | `SourceOS-Linux/TurtleTerm` | Policy-aware terminal commands, trusted execution receipts, `/office` operator flows, evidence inspection, and agent delegation. |
| Browser/collaboration surface | `SourceOS-Linux/BearBrowser` | WOPI launch, web-editor sessions, governed browser automation, download quarantine, workspace mounts, and human/agent browser profiles. |

The historical shorthand `source-os` should not obscure the current implementation split. Current SourceOS host realization is distributed across the SourceOS-Linux repositories above.

## Service set

Planned service surfaces:

- `services/wopi-host/`
- `services/office-collaboration/`
- `services/office-render-convert/`
- `services/office-context-extractor/`
- `services/workspace-ai-orchestrator/`
- `services/office-action-service/`
- `services/workspace-agent-studio/`

## Cross-repo integration

### Upstream product/domain

`SocioProphet/prophet-workspace` defines:

- workspace office capability families
- product parity expectations
- workroom-bound OfficeArtifact contracts
- user-facing and admin-facing semantics
- review posture and side-effect expectations

### Platform runtime

`SocioProphet/prophet-platform` defines and runs:

- editor/document/session runtime contracts
- version/writeback/lock/conflict records
- office collaboration records
- context extraction and indexing workers
- AI action and receipt records
- workflow and automation runtime
- deployment and service topology

### Host and local realization

`SourceOS-Linux/sourceos-devtools`, `SourceOS-Linux/sourceos-shell`, `SourceOS-Linux/TurtleTerm`, and `SourceOS-Linux/BearBrowser` define:

- LibreOffice defaults and local smoke tests
- local extraction hooks and MIME/font integration
- guarded Agent Machine mount behavior
- SourceOS office CLI behavior
- terminal/operator office flows
- browser/WOPI launch and automation flows
- desktop office shell behavior

### Migration and closed-provider exit

`SocioProphet/exodus` owns migration, evidence, and sovereignty planning for movement out of closed vendor control surfaces. Any Google, Microsoft, or Apple source integration belongs to migration/import/export evidence and provider-control scoring unless an explicit policy says otherwise.

## Closed-provider boundary

The core office suite must not depend on Google Workspace, Microsoft 365, Microsoft Graph, or Google APIs for normal operation.

Closed providers may appear only as:

- provenance labels for imported artifacts
- migration/source adapters governed by Exodus
- compatibility test fixtures
- export/import bridges that are disabled by default
- evidence inputs for Exit Readiness Index / Provider Control Surface analysis

Closed providers must not be:

- canonical storage authorities
- required runtime services
- default execution backends
- policy authorities
- collaboration state authorities
- WOPI hot-path dependencies

Schema language should therefore distinguish:

- `source_provider` / provenance: where an artifact came from
- `execution_backend`: the open runtime engine used by SourceOS
- `compatibility_adapter`: a policy-gated bridge for import/export/migration
- `core_authority`: SourceOS/Prophet-owned runtime authority

## First runtime contracts

The first runtime contracts should include:

- `office_document_record`
- `office_session_record`
- `office_collaboration_thread_record`
- `office_suggestion_record`
- `office_version_record`
- `office_writeback_record`
- `office_policy_decision_record`
- `office_adapter_profile`
- `office_ai_action_record`
- `office_ai_receipt_record`
- `workspace_flow_record`

Those contracts should support local desktop and cloud editing paths without binding the product to a single editor implementation or closed provider.

## Current contract paths

Implemented office runtime contract paths:

| Contract | Schema | Example | Purpose |
|---|---|---|---|
| Version | `schemas/office/office_version_record.schema.json` | `schemas/office/examples/office_version_record.example.json` | Captures document version lineage, content refs, content hashes, source provenance, and open execution backend. |
| Writeback | `schemas/office/office_writeback_record.schema.json` | `schemas/office/examples/office_writeback_record.example.json` | Captures WOPI/local saveback operations, lock tokens, base/result versions, conflict state, and receipts. |
| Policy decision | `schemas/office/office_policy_decision_record.schema.json` | `schemas/office/examples/office_policy_decision_record.example.json` | Captures approval/denial/review posture for edits, sends, publishes, imports, exports, and AI side effects. |
| Adapter profile | `schemas/office/office_adapter_profile.schema.json` | `schemas/office/examples/office_adapter_profile.example.json` | Captures open runtime adapters and quarantined closed-provider migration/compatibility adapters. |

Validation entrypoint:

```bash
python3 tools/validate_office_runtime_contracts.py
```

The adapter profile schema enforces that Google Workspace, Microsoft 365, Microsoft Graph, Apple iCloud, and Apple Notes profiles cannot be enabled by default, cannot be runtime dependencies, and cannot be core authority.

## Editor posture

The runtime treats LibreOffice and Collabora as editing/conversion engines, not as the total product. The workspace graph, policy fabric, AI orchestration, receipts, collaboration records, and document-control services belong at the platform layer.

Preferred initial posture:

- LibreOffice: local-first headless generation, render, inspect, and conversion
- Collabora: open browser-collaboration and WOPI-compatible editing path
- SourceOS-native surfaces: future first-party document/app doors
- ONLYOFFICE: optional open deployment compatibility candidate only after policy/license review
- Google/Microsoft: migration/import/export compatibility only, disabled by default and governed through Exodus-style evidence

## Non-goals

- Do not create a monolithic office suite repository.
- Do not vendor an entire editor stack into `prophet-platform`.
- Do not make Google Workspace or Microsoft 365 normal runtime dependencies.
- Do not place memory, semantic extraction, or ontology mutation in the critical WOPI save path.
- Do not treat chat, browser session state, or terminal history as the durable system of record.
