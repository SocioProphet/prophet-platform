---
name: Codex review gate
about: Review gate for a scoped implementation PR
labels: codex-review, review-gate
---

## Scope

Name the PR or implementation issue being reviewed.

## Review focus

- [ ] Branch is current with `main` or explicitly refreshed
- [ ] Scope matches the linked issue
- [ ] Tests cover pass and fail paths where applicable
- [ ] CLI/tooling failures return non-zero where relevant
- [ ] Docs do not overclaim implementation maturity
- [ ] No unrelated product surfaces were mutated

## Required result

Leave one of:

- APPROVE: safe to merge
- REQUEST CHANGES: blocking issues listed below
- COMMENT: non-blocking improvements

## Blocking issues

List exact blockers, if any.

## Merge gate

Do not merge the linked PR until this issue has explicit approval or maintainer override.
