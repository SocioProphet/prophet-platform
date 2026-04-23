# WOPI Host Profile

This document defines the first runtime profile for the office cloud suite WOPI host in `prophet-platform`.

## Purpose

The WOPI host is the boundary between the cloud editor and the document/storage control plane.

It should provide the minimum office edit/view contract for:
- cloud editor launch
- file metadata and capability discovery
- file retrieval
- file writeback
- locks and lock refresh
- version-aware saveback
- conflict handling and retry surfaces

## Responsibilities

The WOPI host should own:
- document-scoped access token validation
- `CheckFileInfo`
- `GetFile`
- `PutFile`
- `PutRelativeFile`
- `Lock`
- `Unlock`
- `UnlockAndRelock`
- `RefreshLock`

## Object bindings

The WOPI host should be backed by:
- `office_document_record`
- `office_session_record`
- version and writeback records
- office AI receipts and action gating where editor-originating actions trigger AI follow-ons

## Cross-repo integration

### `prophet-workspace`
Defines product semantics for cloud editing, saveback, versioning, comments, and collaboration expectations.

### `source-os`
Defines local/cloud handoff behavior for opening documents into cloud edit sessions.

### `memory-mesh`
Optional recall/writeback hooks should not be in the critical editor save path, but may attach before or after explicit AI actions.

### `ontogenesis`
Semantic unit and graph boundary mappings should apply after extraction and version capture, not in the hot path of WOPI RPC handling.

## First implementation rule

The first WOPI host implementation should be narrow and explicit. It should prefer correctness and inspectability over breadth.
