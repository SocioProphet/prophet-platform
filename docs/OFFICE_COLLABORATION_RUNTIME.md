# Office Collaboration Runtime

This document defines the runtime slice for office collaboration records in `prophet-platform`.

## Purpose

The office/workspace product already needs collaboration objects such as:

- comment/review threads
- suggestions
- review state
- version-aware review history
- policy-safe agent-created collaboration objects

This runtime slice gives those product objects a concrete platform home without making chat history, browser session state, or editor-local metadata the durable collaboration authority.

## Runtime responsibilities

`prophet-platform` owns:

- collaboration record storage and retrieval
- version linkage for collaboration objects
- runtime service seams for comments and suggestions
- audit/evidence linkage for agent-created collaboration objects
- permission-aware retrieval and mutation
- collaboration state transitions for review and resolution flows

## First runtime records

- `office_collaboration_thread_record`
- `office_suggestion_record`

Follow-up records should include:

- collaboration message/reply records
- version-aware review state records
- policy decision records for external publish/share/send side effects
- receipt records for agent-authored comments or suggestions

## First service seam

`services/office-collaboration/` should be able to:

- create and fetch collaboration threads
- create and resolve suggestions
- bind collaboration records to office artifacts and versions
- preserve receipts and policy-safe side effects
- expose health and smoke surfaces for deterministic runtime validation

## Cross-repo boundaries

- `SocioProphet/prophet-workspace` owns the product collaboration model and workroom semantics.
- `SocioProphet/prophet-platform` owns runtime records, service seams, version linkage, receipts, and permission-aware mutation.
- `SourceOS-Linux/sourceos-shell`, `SourceOS-Linux/sourceos-devtools`, `SourceOS-Linux/TurtleTerm`, and `SourceOS-Linux/BearBrowser` own local/cloud handoff affordances, CLI/operator/browser surfaces, and guarded local execution. They do not own canonical collaboration storage.
- `SocioProphet/exodus` owns closed-provider migration and sovereignty evidence when imported Google/Microsoft/Apple artifacts or metadata are involved.

## Closed-provider boundary

Google Workspace, Microsoft 365, and Microsoft Graph are not collaboration-state authorities for the SourceOS office suite. They may be represented only as provenance/import/export compatibility sources under explicit policy and migration evidence.

The canonical collaboration state for SourceOS office artifacts remains in open Prophet/SourceOS records, version links, receipts, and policy decisions.
