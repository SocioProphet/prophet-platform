# WOPI Host Profile

This document defines the first runtime profile for the open office cloud-suite WOPI host in `prophet-platform`.

## Purpose

The WOPI host is the boundary between an editor surface and the document/storage control plane.

It should provide the minimum office edit/view contract for:

- cloud editor launch
- file metadata and capability discovery
- file retrieval
- file writeback
- locks and lock refresh
- version-aware saveback
- conflict handling and retry surfaces

The WOPI host is not the total office product. It is a narrow, testable runtime seam inside the broader SourceOS office suite.

## Responsibilities

The WOPI host owns:

- document-scoped access token validation
- `CheckFileInfo`
- `GetFile`
- `PutFile`
- `PutRelativeFile`
- `Lock`
- `Unlock`
- `UnlockAndRelock`
- `RefreshLock`
- conflict-safe writeback handoff to version/writeback records

## Object bindings

The WOPI host should be backed by:

- `office_document_record`
- `office_session_record`
- version and writeback records
- policy decision records for side effects
- office AI receipts and action gating where editor-originating actions trigger AI follow-ons

## Cross-repo integration

### `SocioProphet/prophet-workspace`

Defines product semantics for office artifacts, cloud editing, saveback, versioning, comments, review state, and collaboration expectations.

### `SocioProphet/prophet-platform`

Defines and runs the WOPI host, document/session/version/writeback records, collaboration runtime, service health surfaces, and deployment topology.

### SourceOS host surfaces

`SourceOS-Linux/sourceos-shell`, `SourceOS-Linux/sourceos-devtools`, `SourceOS-Linux/TurtleTerm`, and `SourceOS-Linux/BearBrowser` define local/cloud handoff behavior for opening documents into editor sessions, inspecting office evidence, launching WOPI/browser sessions, and guarding local output/download roots.

### `memory-mesh`

Optional recall/writeback hooks should not be in the critical editor save path. They may attach before or after explicit AI actions and after version capture.

### `ontogenesis`

Semantic unit and graph boundary mappings should apply after extraction and version capture, not in the hot path of WOPI RPC handling.

### `SocioProphet/exodus`

Closed-provider import/export/migration state belongs to Exodus-style migration evidence. Google Workspace, Microsoft 365, Microsoft Graph, and Apple provider surfaces must not become WOPI hot-path dependencies or durable office authorities.

## First implementation rule

The first WOPI host implementation should be narrow and explicit. It should prefer correctness and inspectability over breadth.

Initial acceptance posture:

- one open editor binding
- one storage backend seam
- explicit lock semantics
- explicit version/writeback records
- explicit conflict-state behavior
- health and smoke surfaces suitable for CI
- no Google/Microsoft runtime dependency
- no semantic extraction or memory mutation inside the critical save path
