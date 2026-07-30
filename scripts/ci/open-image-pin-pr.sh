#!/usr/bin/env bash
#
# Open (or refresh) the search-orchestrator image-pin pull request, without a
# third-party action.
#
# WHY THIS EXISTS INSTEAD OF `peter-evans/create-pull-request`
# ------------------------------------------------------------
# This repo restricts Actions to `allowed_actions: selected` — github-owned, plus
# verified-creator Marketplace actions, plus an explicit pattern allowlist
# (dtolnay/*, Swatinem/*, oven-sh/*, tauri-apps/*). `peter-evans/create-pull-request`
# is Marketplace-listed, but its creator is an individual with no verified-creator
# badge, so `verified_allowed` does not cover it, and it matches no pattern.
#
# A workflow that references a blocked action is rejected at run creation, before
# any job starts: conclusion `startup_failure`, no logs, no annotation, no alert.
# search-orchestrator-image-pin.yml succeeded once (2026-04-26) and then failed
# that way nine times in a row (2026-07-03 .. 2026-07-20) without one character of
# the file changing — the policy moved underneath it on 2026-06-23. The other two
# actions it uses, actions/checkout and actions/download-artifact, are
# github-owned and were never affected.
#
# The alternative fix — an admin adding `peter-evans/*` to patterns_allowed — is a
# repository settings change: invisible in a diff, unreviewable in a PR, and it
# re-grants a third party code execution against the workflow token. It was
# rejected for exactly that reason in the OpenTofu case (PRs #1090 and #1097, see
# scripts/ci/install-opentofu.sh). This follows that precedent.
#
# BEHAVIOUR (matching what the action did, minus the third party)
# ---------------------------------------------------------------
#   * Commits ONLY the two pin paths — the action's `add-paths`. The evidence
#     artifact downloaded into image-evidence/ never enters the commit.
#   * No digest change is the normal case, and is a silent success, not a failure.
#   * The automation branch is reused and reset, so repeated builds refresh one
#     pull request instead of opening a pile of them.
#
# THE GITHUB_TOKEN CONSEQUENCE — read before changing the dispatch below
# ----------------------------------------------------------------------
# A pull request opened with GITHUB_TOKEN does not start `pull_request` workflow
# runs. That is GitHub's no-recursion rule, and it is deliberate. In this repo the
# `main-required-checks` ruleset requires exactly one context, `diagnostics-gate`,
# so a PR opened here gets no gate, and cannot merge — permanently BLOCKED, with a
# handful of green GitHub-App checks (CodeQL, GitGuardian) making it look ready.
# Measured on real PRs: #1007/#1013 (zero runs) and #1017/#1018 (runs parked at
# action_required, which publish no check-runs). gitops-promote.yml carries the
# full write-up.
#
# workflow_dispatch is the documented exception: an explicit dispatch does create
# a run under GITHUB_TOKEN, and is not a pull_request event, so it is not subject
# to the contributor-approval gate either. Its check-runs attach to the branch
# head, which is the PR head, so `diagnostics-gate` lands on the PR rollup.
# That is why this script dispatches, and why the workflow needs `actions: write`.
# Removing the dispatch does not make the PR "slightly worse" — it makes every PR
# this workflow opens unmergeable.

set -euo pipefail

BASE="${PIN_PR_BASE:-main}"
BRANCH="${PIN_PR_BRANCH:-automation/search-orchestrator-image-pin}"
TITLE="release(search): pin search orchestrator image digest"
DIAGNOSTICS_WORKFLOW="${PIN_PR_DIAGNOSTICS_WORKFLOW:-validate-target-diagnostics.yml}"
# Overridable so the self-test does not spend 20 real seconds proving the retry.
RETRY_SLEEP="${PIN_PR_RETRY_SLEEP:-10}"

PIN_PATHS=(
  "releases/images/search-orchestrator.image-lock.json"
  "infra/k8s/search-orchestrator/overlays/policy/image-patch.yaml"
)

# ── Nothing to pin ───────────────────────────────────────────────────────────
# The digest already matches. This is the common outcome for a rebuild of an
# unchanged tree, and it must not look like a failure.
if [ -z "$(git status --porcelain -- "${PIN_PATHS[@]}")" ]; then
  echo "no digest change: the lock and the Kustomize patch already match this build"
  echo "nothing to open"
  exit 0
fi

echo "digest change detected in:"
git status --porcelain -- "${PIN_PATHS[@]}" | sed 's/^/  /'

# ── Commit, on a reset automation branch ─────────────────────────────────────
git config user.name "search-orchestrator-image-pin"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git checkout -b "$BRANCH"
# Explicit pathspec, never `git commit -a`: image-evidence/ and anything else the
# job leaves in the tree stays out. This is the `add-paths` guarantee.
git add -- "${PIN_PATHS[@]}"
git commit -m "$TITLE"

# --force: this is a reusable automation ref that may still hold a now-stale
# digest from an earlier build. The action reset it the same way. Nothing but
# this job writes under automation/.
git push --force origin "HEAD:refs/heads/$BRANCH"

# ── Open the PR, or reuse the one that is already open ───────────────────────
open_pr() {
  gh pr list --head "$BRANCH" --base "$BASE" --state open \
    --json number --jq '.[0].number // empty'
}

pr="$(open_pr)"
if [ -n "$pr" ]; then
  echo "PR #$pr is already open for $BRANCH; the refreshed pin was pushed onto it"
else
  gh pr create --base "$BASE" --head "$BRANCH" --title "$TITLE" --body "$(
    cat <<'BODY'
## Summary

Pins the Search Orchestrator image digest from the successful `search-orchestrator-image`
workflow run.

## Scope

- Updates `releases/images/search-orchestrator.image-lock.json`
- Updates the digest-pinned Kustomize image patch
- Keeps the example lock unchanged

## Safety posture

- Digest pin only
- No runtime route behavior change
- No learner action execution
- No Canon promotion
- No policy grant creation
- No memory writeback

## How this PR gets its required check

This PR was opened by CI with `GITHUB_TOKEN`. **A pull request opened that way does
not start `pull_request` workflow runs** — GitHub's no-recursion rule. The
`main-required-checks` ruleset requires `diagnostics-gate`, so left alone this PR
would sit BLOCKED forever, while unrelated GitHub-App checks (CodeQL, GitGuardian)
go green and make it look mergeable. It is not: a green rollup of those alone is a
mirage.

So the job that opened this PR also dispatches `validate-target-diagnostics.yml`
onto this branch explicitly. `workflow_dispatch` is the documented exception to
the no-recursion rule, and its check-runs attach to this branch head, which is
this PR's head — so `diagnostics-gate` appears here and the ruleset is satisfied.

**If `diagnostics-gate` is missing below**, the dispatch failed (the job logs a
warning when it does). Produce it with:

```
gh workflow run validate-target-diagnostics.yml --ref automation/search-orchestrator-image-pin
```

Do not "push an empty commit to kick CI" — that is the manual workaround the
dispatch replaces.
BODY
  )"
  pr="$(open_pr)"
  echo "opened PR #${pr:-<unknown>} for $BRANCH"
fi

# ── Give the PR the one check that is actually required ──────────────────────
# Unattended job: a dispatch that quietly fails leaves the PR BLOCKED until a
# human happens to look. A freshly pushed ref can also take a moment to become
# dispatchable, hence the retry.
dispatched=""
for attempt in 1 2 3; do
  if gh workflow run "$DIAGNOSTICS_WORKFLOW" --ref "$BRANCH"; then
    dispatched=1
    echo "dispatched $DIAGNOSTICS_WORKFLOW onto $BRANCH (attempt $attempt)"
    break
  fi
  echo "dispatch attempt $attempt failed; retrying in ${RETRY_SLEEP}s"
  sleep "$RETRY_SLEEP"
done

if [ -z "$dispatched" ]; then
  echo "::warning::could not dispatch $DIAGNOSTICS_WORKFLOW onto $BRANCH after 3 attempts. PR #${pr:-<unknown>} will stay BLOCKED, because diagnostics-gate is required and a GITHUB_TOKEN pull request does not produce it on its own. Recover with: gh workflow run $DIAGNOSTICS_WORKFLOW --ref $BRANCH"
fi
