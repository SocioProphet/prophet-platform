#!/usr/bin/env bash
#
# Self-test for scripts/ci/open-image-pin-pr.sh.
#
# The script it guards runs unattended, on a trigger no pull request fires, and it
# force-pushes a branch and opens a PR. That combination is exactly how
# search-orchestrator-image-pin.yml managed to be broken from 2026-06-23 to
# 2026-07-20 without anyone noticing. So the logic gets a test that needs no
# network, no secrets and no GitHub: a throwaway git repo, and a `gh` stub on PATH
# that records what it was asked to do.
#
# What is genuinely covered: the no-op exit, commit path-scoping, branch reset,
# create-vs-refresh, and the diagnostics dispatch including its failure warning.
# What is NOT covered: that the real `gh` accepts these arguments, and that the
# real API behaves as expected. Those need a live run.

set -euo pipefail

SCRIPT_UNDER_TEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/open-image-pin-pr.sh"
[ -x "$SCRIPT_UNDER_TEST" ] || { echo "FAIL: $SCRIPT_UNDER_TEST is not executable"; exit 1; }

LOCK="releases/images/search-orchestrator.image-lock.json"
PATCH="infra/k8s/search-orchestrator/overlays/policy/image-patch.yaml"

WORKROOT="$(mktemp -d)"
trap 'rm -rf "$WORKROOT"' EXIT

failures=0
pass() { echo "  ok   — $1"; }
fail() { echo "  FAIL — $1"; failures=$((failures + 1)); }

# A `gh` that logs its arguments and answers `pr list` from the environment.
make_gh_stub() {
  local dir="$1"
  mkdir -p "$dir"
  cat >"$dir/gh" <<'STUB'
#!/usr/bin/env bash
# One line per invocation. `gh pr create --body` carries a multi-line body, and
# logging it verbatim put lines like "workflow run." — wrapped prose from the body
# — at the start of a log line, where a `^workflow run` assertion counted it as a
# fourth dispatch. Flatten first, then assertions mean what they look like.
printf '%s\n' "$(printf '%s' "$*" | tr '\n' ' ')" >>"$GH_LOG"
case "$1 ${2:-}" in
  "pr list")     printf '%s' "${STUB_OPEN_PR:-}" ;;
  "pr create")   echo "https://github.com/SocioProphet/prophet-platform/pull/9999" ;;
  "workflow run") exit "${STUB_DISPATCH_RC:-0}" ;;
esac
exit 0
STUB
  chmod +x "$dir/gh"
}

# A repo with an origin to push to, the two pin paths committed, and the script
# available at the path the workflow calls it by.
new_case() {
  local name="$1"
  CASE_DIR="$WORKROOT/$name"
  mkdir -p "$CASE_DIR"
  git init --quiet --bare "$CASE_DIR/origin.git"
  git clone --quiet "$CASE_DIR/origin.git" "$CASE_DIR/work"
  cd "$CASE_DIR/work"
  git config user.email seed@example.invalid
  git config user.name seed
  git config init.defaultBranch main >/dev/null 2>&1 || true
  git checkout --quiet -b main 2>/dev/null || true
  mkdir -p "$(dirname "$LOCK")" "$(dirname "$PATCH")"
  echo '{"digest":"sha256:old"}' >"$LOCK"
  echo 'image: old' >"$PATCH"
  git add -A && git commit --quiet -m "seed"
  git push --quiet -u origin main >/dev/null 2>&1

  GH_LOG="$CASE_DIR/gh.log"
  : >"$GH_LOG"
  make_gh_stub "$CASE_DIR/bin"
  export GH_LOG
  export PATH="$CASE_DIR/bin:$PATH"
  export PIN_PR_RETRY_SLEEP=0
  unset STUB_OPEN_PR STUB_DISPATCH_RC || true
}

run_script() {
  set +e
  OUT="$("$SCRIPT_UNDER_TEST" 2>&1)"
  RC=$?
  set -e
}

echo "case 1: no digest change is a silent success"
new_case nochange
run_script
[ "$RC" -eq 0 ] || fail "expected exit 0, got $RC"
grep -q "no digest change" <<<"$OUT" || fail "expected the no-op message; got: $OUT"
[ ! -s "$GH_LOG" ] || fail "gh must not be called when there is nothing to pin; got: $(cat "$GH_LOG")"
git -C "$CASE_DIR/origin.git" show-ref --quiet refs/heads/automation/search-orchestrator-image-pin \
  && fail "no automation branch should have been pushed" \
  || pass "no-op: exits 0, touches nothing"

echo "case 2: a digest change opens a PR and dispatches the gate"
new_case create
echo '{"digest":"sha256:new"}' >"$LOCK"
echo 'image: new' >"$PATCH"
run_script
[ "$RC" -eq 0 ] || fail "expected exit 0, got $RC — $OUT"
git -C "$CASE_DIR/origin.git" show-ref --quiet refs/heads/automation/search-orchestrator-image-pin \
  || fail "the automation branch was not pushed"
grep -q "^pr create" "$GH_LOG" || fail "gh pr create was not called"
grep -q "^workflow run validate-target-diagnostics.yml" "$GH_LOG" \
  || fail "the diagnostics gate was not dispatched"
grep -q -- "--ref automation/search-orchestrator-image-pin" "$GH_LOG" \
  || fail "the dispatch did not target the automation branch"
[ "$failures" -eq 0 ] && pass "create: branch pushed, PR opened, gate dispatched"

echo "case 3: only the pin paths are committed"
new_case scoped
echo '{"digest":"sha256:new"}' >"$LOCK"
echo 'image: new' >"$PATCH"
mkdir -p image-evidence && echo 'downloaded artifact' >image-evidence/search-orchestrator-image.json
echo 'unrelated dirty file' >NOTES.txt
run_script
[ "$RC" -eq 0 ] || fail "expected exit 0, got $RC — $OUT"
committed="$(git -C "$CASE_DIR/work" show --name-only --format= HEAD | sort | tr '\n' ' ')"
case "$committed" in
  *image-evidence*) fail "the evidence artifact was committed: $committed" ;;
  *NOTES.txt*)      fail "an unrelated file was committed: $committed" ;;
  *)                pass "scoping: committed only [$committed]" ;;
esac

echo "case 4: an already-open PR is refreshed, not duplicated"
new_case refresh
echo '{"digest":"sha256:new"}' >"$LOCK"
echo 'image: new' >"$PATCH"
export STUB_OPEN_PR=4242
run_script
[ "$RC" -eq 0 ] || fail "expected exit 0, got $RC — $OUT"
grep -q "^pr create" "$GH_LOG" && fail "a second PR was opened over an existing one"
grep -q "#4242 is already open" <<<"$OUT" || fail "the existing PR was not reported; got: $OUT"
grep -q "^workflow run" "$GH_LOG" || fail "the gate must still be dispatched on a refresh"
unset STUB_OPEN_PR
[ "$failures" -eq 0 ] && pass "refresh: reuses PR #4242, still dispatches"

echo "case 5: a failed dispatch warns loudly instead of passing quietly"
new_case dispatchfail
echo '{"digest":"sha256:new"}' >"$LOCK"
echo 'image: new' >"$PATCH"
export STUB_DISPATCH_RC=1
run_script
[ "$RC" -eq 0 ] || fail "a failed dispatch should not fail the job, got $RC"
grep -q "::warning::" <<<"$OUT" || fail "no warning annotation on dispatch failure; got: $OUT"
grep -q "BLOCKED" <<<"$OUT" || fail "the warning must say the PR will be BLOCKED"
[ "$(grep -c '^workflow run' "$GH_LOG")" -eq 3 ] || fail "expected 3 dispatch attempts, got $(grep -c '^workflow run' "$GH_LOG")"
unset STUB_DISPATCH_RC
[ "$failures" -eq 0 ] && pass "dispatch failure: 3 attempts, warns, does not fail the job"

echo
if [ "$failures" -ne 0 ]; then
  echo "$failures check(s) FAILED"
  exit 1
fi
echo "all pin-PR checks passed"
