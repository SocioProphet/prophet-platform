---
name: Copilot implementation task
about: Scoped implementation work intended for Copilot
labels: copilot, scoped-work
---

## Scope

State the narrow implementation slice. This should be one PR-sized unit.

## Expected files

- `path/to/file`

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests cover pass and fail paths where applicable
- [ ] CI workflow is updated only if needed

## Non-goals

- Do not broaden beyond this issue.
- Do not mutate unrelated product surfaces.
- Do not overclaim production readiness.

## Copilot implementation instruction

Keep the PR narrow, additive when possible, and based on current `main`. Avoid stale branch replay.

## Codex review checklist

- Confirm branch is current with `main`.
- Confirm scope matches this issue.
- Confirm CLI/tooling failures return non-zero where relevant.
- Confirm tests exercise expected behavior.
- Confirm docs are accurate and do not overclaim.
