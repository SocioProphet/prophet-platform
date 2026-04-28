# Copilot Remediation and Large-Change Review Policy

Status: active process policy
Date: 2026-04-28
Owner surface: Prophet Platform / cross-repo program governance

## Purpose

Define the default process for using GitHub Copilot coding agent during cross-repo GAIA / OSM / MeshRush / Agentplane / Lattice / SocioSphere work.

## Policy

### 1. Failed checks and conflicts

When a pull request has failed checks, stale branch protection contexts, merge conflicts, or workflow-context mismatches, request Copilot remediation before spending additional manual implementation turns.

Default comment pattern:

```text
@copilot please resolve the failing checks/conflicts on this PR. Preserve the existing contract semantics unless a CI fix requires a minimal workflow/configuration change. Summarize root cause and fix.
```

### 2. Large changes require review

Any PR or commit set over 500 changed lines requires an explicit review request before merge.

Review should focus on:

- contract semantics;
- safety and approval boundaries;
- workflow/check behavior;
- governance invariants;
- backwards compatibility;
- source/provenance preservation;
- whether the change should be split before merge.

Default comment pattern:

```text
@copilot please review this PR before merge because the changed-line count is over 500 lines. Focus on contract semantics, safety boundaries, validation coverage, and workflow behavior.
```

### 3. Scope discipline

Copilot remediation must not expand product scope. It should fix the specific failed check, merge conflict, or review concern.

### 4. Closure discipline

For P0 closure work, use Copilot to clear blocking checks or conflicts while the main workstream continues only on remaining P0 verification items.

Do not expand into Smart Spaces, Lattice runtime admission, live OSM ingestion, production tile generation, or safety-critical navigation until P0 closure criteria are complete.
