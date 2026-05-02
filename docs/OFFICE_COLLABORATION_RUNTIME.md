# Office Collaboration Runtime

This document defines the runtime slice for office collaboration records in `prophet-platform`.

## Purpose

The office/workspace product already needs collaboration objects such as:
- comment/review threads
- suggestions
- review state

This runtime slice gives those product objects a concrete platform home.

## Runtime responsibilities

`prophet-platform` should own:
- collaboration record storage and retrieval
- version linkage for collaboration objects
- runtime service seams for comments and suggestions
- audit/evidence linkage for agent-created collaboration objects
- permission-aware retrieval and mutation

## First runtime records

- `office_collaboration_thread_record`
- `office_suggestion_record`

## First service seam

A later `services/office-collaboration/` runtime should be able to:
- create and fetch collaboration threads
- create and resolve suggestions
- bind collaboration records to office artifacts and versions
- preserve receipts and policy-safe side effects

## Cross-repo boundaries

- `prophet-workspace` owns the product collaboration model
- `prophet-platform` owns runtime records and service seams
- `source-os` owns local/cloud handoff affordances, not canonical collaboration storage
