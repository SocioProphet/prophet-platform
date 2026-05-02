# Office Collaboration Service

This directory is the runtime stub for office collaboration in `prophet-platform`.

## Purpose

The office collaboration service should eventually provide the runtime seam for:
- comment/review threads
- suggestions
- review state transitions
- version-aware collaboration history

## Backing records

- `schemas/office/office_collaboration_thread_record.schema.json`
- `schemas/office/office_suggestion_record.schema.json`

## Cross-repo posture

- product semantics live in `SocioProphet/prophet-workspace`
- runtime storage/execution lives in `SocioProphet/prophet-platform`
- local/cloud affordances live in `SociOS-Linux/source-os`
