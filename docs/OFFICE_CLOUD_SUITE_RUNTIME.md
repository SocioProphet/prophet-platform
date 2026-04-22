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

## Service set

Planned service surfaces:
- `services/wopi-host/`
- `services/office-render-convert/`
- `services/office-context-extractor/`
- `services/workspace-ai-orchestrator/`
- `services/office-action-service/`
- `services/workspace-agent-studio/`

## Cross-repo integration

### Upstream product/domain

`SocioProphet/prophet-workspace` should define:
- workspace office capability families
- product parity expectations
- user-facing and admin-facing semantics

### Downstream host realization

`SociOS-Linux/source-os` should define:
- LibreOffice defaults
- local extraction hooks
- local smoke tests
- font and MIME integration
- desktop office shell behavior

## First runtime contracts

The first runtime contracts should include:
- office document record
- office AI action record
- office AI receipt record
- workspace flow record

Those contracts should support local desktop and cloud editing paths without binding the product to a single editor implementation.

## Editor posture

The runtime should treat LibreOffice / Collabora as an editing and conversion engine, not as the total product. The workspace graph, AI orchestration, and document-control services belong at the platform layer.
