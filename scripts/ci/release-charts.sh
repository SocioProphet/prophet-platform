#!/usr/bin/env bash
#
# Publish charts/* as a Helm repo on the gh-pages branch, using the `cr` binary
# installed by scripts/ci/install-chart-releaser.sh.
#
# This is the orchestration that `helm/chart-releaser-action` used to do. That
# action cannot run here (see install-chart-releaser.sh for why), so the same
# three `cr` calls are made directly.
#
#   --package-only   package the charts and stop. No token, no writes, no
#                    releases. This is what runs on a pull request, so a change
#                    to this script or to the workflow is exercised before it
#                    merges instead of only being discovered on main.
#
# Deliberate difference from the action: the action diffed charts against the
# latest tag and uploaded only what changed. Here every chart is packaged and
# `cr upload --skip-existing` drops the ones already released. Same outcome,
# but it does not depend on tag history being intact, and re-running is a no-op
# rather than a failure.

set -euo pipefail

PACKAGE_ONLY=0
case "${1:-}" in
  --package-only) PACKAGE_ONLY=1 ;;
  "") ;;
  *) echo "::error::unknown argument '$1' (expected --package-only or nothing)" >&2; exit 1 ;;
esac

PKG_DIR=".cr-release-packages"
rm -rf "$PKG_DIR" && mkdir -p "$PKG_DIR"

found=0
for chart in charts/*/; do
  [ -f "${chart}Chart.yaml" ] || continue
  echo "Packaging ${chart}"
  cr package "$chart" --package-path "$PKG_DIR"
  found=1
done

if [ "$found" -eq 0 ]; then
  echo "::error::no chart found under charts/ -- refusing to report success for publishing nothing" >&2
  exit 1
fi

ls -l "$PKG_DIR"

if [ "$PACKAGE_ONLY" -eq 1 ]; then
  echo "--package-only: packaged $(find "$PKG_DIR" -name '*.tgz' | wc -l | tr -d ' ') chart(s), not publishing."
  exit 0
fi

: "${CR_TOKEN:?CR_TOKEN must be set to publish}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
: "${GITHUB_SHA:?GITHUB_SHA must be set}"
OWNER="${GITHUB_REPOSITORY%%/*}"
REPO="${GITHUB_REPOSITORY##*/}"
PAGES_BRANCH="${CR_PAGES_BRANCH:-gh-pages}"

# `cr index --push` publishes by running `git worktree add --detach <dir>
# origin/<pages-branch>`, so the branch has to already exist -- otherwise the
# push fails on an unresolvable ref. Creating it empty is the one-time manual
# setup step chart-releaser documents; do it here so the first run works rather
# than failing on a prerequisite nobody is watching for.
if ! git ls-remote --exit-code --heads origin "$PAGES_BRANCH" >/dev/null 2>&1; then
  echo "Branch '${PAGES_BRANCH}' does not exist yet; creating it with an empty index."
  wt="$(mktemp -d)/${PAGES_BRANCH}"
  git worktree add --detach "$wt"
  git -C "$wt" checkout --orphan "$PAGES_BRANCH"
  git -C "$wt" rm -rq --cached . || true
  find "$wt" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  : > "$wt/index.yaml"
  git -C "$wt" add index.yaml
  git -C "$wt" commit -m "chore(charts): initialise Helm chart repository index"
  git -C "$wt" push origin "$PAGES_BRANCH"
  git worktree remove --force "$wt"
  git fetch origin "${PAGES_BRANCH}:refs/remotes/origin/${PAGES_BRANCH}"
fi

cr upload \
  --owner "$OWNER" \
  --git-repo "$REPO" \
  --package-path "$PKG_DIR" \
  --pages-branch "$PAGES_BRANCH" \
  --commit "$GITHUB_SHA" \
  --token "$CR_TOKEN" \
  --skip-existing

cr index \
  --owner "$OWNER" \
  --git-repo "$REPO" \
  --package-path "$PKG_DIR" \
  --pages-branch "$PAGES_BRANCH" \
  --index-path .cr-index/index.yaml \
  --token "$CR_TOKEN" \
  --push
