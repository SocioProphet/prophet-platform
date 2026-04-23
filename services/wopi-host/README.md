# WOPI Host Service

This directory is the runtime stub for the office cloud suite WOPI host.

## Service purpose

The WOPI host is responsible for the document/editor boundary used by the cloud office suite.

## Planned responsibilities

- document-scoped access token validation
- file info retrieval
- file read and writeback
- lock and unlock handling
- conflict-aware save behavior
- launch surfaces for the cloud editor

## Backing contracts

- `schemas/office/office_document_record.schema.json`
- `schemas/office/office_session_record.schema.json`
- later: version, receipt, and writeback records

## Cross-repo boundaries

- product semantics live in `SocioProphet/prophet-workspace`
- Linux/desktop handoff lives in `SociOS-Linux/source-os`
- local memory and search dependencies should stay outside the hot path of editor RPC handling

## First implementation posture

The first implementation should be narrow and testable:
- one editor binding
- one storage backend seam
- explicit lock semantics
- explicit health and smoke surfaces
