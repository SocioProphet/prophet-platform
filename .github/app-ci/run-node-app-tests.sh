#!/usr/bin/env bash
#
# node-app-suites: run every apps/* suite that uses the Node built-in test runner
# (`node --test`), one leg for all of them, each under a HARD per-app timeout so a
# hang surfaces as a RED check (exit 124) and never as a silently cancelled job.
#
# This script is the whole charter of the `node-app-suites` matrix leg in
# .github/workflows/validate-target-diagnostics.yml. It deliberately lives OUTSIDE
# tools/ (contested) and is invoked as `bash .github/app-ci/run-node-app-tests.sh`.
#
# Invariants it enforces (each one turns the required diagnostics-gate RED):
#   1. ZERO-MATCH IS A FAILURE. If no app declares a `node --test` script, coverage
#      has been silently dropped (harness renamed / discovery broken). Refuse to pass.
#      A present-but-unparseable package.json is likewise fatal, never a silent skip.
#   2. QUARANTINE ONLY SHRINKS. .github/app-ci/quarantine.json carries a ceiling;
#      len(quarantined) must be <= ceiling AND, vs the origin/main baseline, the
#      ceiling may not rise and no new app may be added — a mechanical ratchet, not
#      reviewer friction. A newly-failing suite must be FIXED, not quarantined.
#   3. NO STALE QUARANTINE. A quarantined app must still exist and still declare a
#      test script, or the entry must be pruned (and the ceiling lowered).
#   4. SOMETHING MUST RUN. If every discovered app is quarantined, the leg would pass
#      without testing anything — that is a failure, not a green.
#
# Env seams (used by local red/green proofs; defaults are the CI values):
#   PER_APP_TIMEOUT           hard per-app timeout in seconds   (default 180)
#   APPS_GLOB                 package.json glob to discover      (default apps/*/package.json)
#   QUARANTINE_FILE           path to the quarantine allowlist   (default .github/app-ci/quarantine.json)
#   QUARANTINE_BASELINE_REF   git ref the ratchet diffs against  (default origin/main)
#   QUARANTINE_BASELINE_FILE  baseline quarantine from a file    (local ratchet proofs)
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PER_APP_TIMEOUT="${PER_APP_TIMEOUT:-180}"
APPS_GLOB="${APPS_GLOB:-apps/*/package.json}"
QUARANTINE_FILE="${QUARANTINE_FILE:-$REPO_ROOT/.github/app-ci/quarantine.json}"

# Read a package.json's test script (absolute path in, script text out; empty when
# the manifest is VALID but declares no test). A missing or UNPARSEABLE manifest is
# not "no tests": it exits non-zero (3) with a reason on stderr, so the caller fails
# RED instead of silently dropping the app's coverage — the exact silent omission
# this leg exists to stop.
read_test_script() {
  node -e '
    const fs=require("fs"), path=require("path");
    let raw;
    try { raw = fs.readFileSync(path.resolve(process.argv[1]),"utf8"); }
    catch(e) { process.stderr.write("unreadable: "+e.message); process.exit(3); }
    let p;
    try { p = JSON.parse(raw); }
    catch(e) { process.stderr.write("invalid JSON: "+e.message); process.exit(3); }
    process.stdout.write(((p&&p.scripts&&p.scripts.test)||""));
  ' "$1"
}

# ---------------------------------------------------------------------------
# 1. Discover apps that declare a test script, and partition by test harness.
# ---------------------------------------------------------------------------
NODE_APPS=()      # test script uses the Node built-in runner  -> this leg runs them
OTHER_APPS=()     # test script uses another harness (vitest…) -> reported, not run here
shopt -s nullglob
for pj in $APPS_GLOB; do
  [ -f "$pj" ] || continue
  app="$(basename "$(dirname "$pj")")"
  script="$(read_test_script "$pj")"; rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FATAL: apps/$app/package.json is present but unreadable/unparseable, so its"
    echo "       test coverage cannot be determined. This leg refuses to treat a broken"
    echo "       manifest as 'no tests' and silently drop the app. Fix the manifest."
    exit 1
  fi
  [ -z "$script" ] && continue
  if [[ "$script" == *"node "*"--test"* || "$script" == *"node --test"* ]]; then
    NODE_APPS+=("$app")
  else
    OTHER_APPS+=("$app  [${script}]")
  fi
done
shopt -u nullglob

# Invariant 1: zero matches is a FAILURE, never a skip.
if [ "${#NODE_APPS[@]}" -eq 0 ]; then
  echo "FATAL: no apps/* declare a 'node --test' test script (glob: $APPS_GLOB)."
  echo "       Either the harness was renamed (coverage silently dropped) or discovery"
  echo "       is broken. This leg refuses to report success on zero matches."
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Load and validate the SHRINKING quarantine allowlist.
# ---------------------------------------------------------------------------
if [ ! -f "$QUARANTINE_FILE" ]; then
  echo "FATAL: quarantine file not found: $QUARANTINE_FILE"; exit 1
fi
CEILING="$(node -e 'const fs=require("fs");const q=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));process.stdout.write(String(q.ceiling))' "$QUARANTINE_FILE")"
Q_APPS=()
while IFS= read -r line; do [ -n "$line" ] && Q_APPS+=("$line"); done < <(
  node -e 'const fs=require("fs");const q=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));for(const k of Object.keys(q.apps||{}))console.log(k)' "$QUARANTINE_FILE"
)

if ! [[ "$CEILING" =~ ^[0-9]+$ ]]; then
  echo "FATAL: quarantine ceiling is not a number: '$CEILING'"; exit 1
fi

# Invariant 2: len(quarantined) must be within the ceiling declared in the file.
if [ "${#Q_APPS[@]}" -gt "$CEILING" ]; then
  echo "FATAL: quarantine holds ${#Q_APPS[@]} app(s) but the ceiling is $CEILING."
  echo "       len(apps) must be <= ceiling. Remove an app and/or lower the ceiling."
  exit 1
fi

# Invariant 2b: the ratchet may only SHRINK versus the baseline. len<=ceiling within
# one file cannot stop a PR that adds an app AND raises the ceiling in the same diff —
# both edits land together and pass. Compare against the baseline (origin/main by
# default): the ceiling may not rise and no new app key may appear. A newly-failing
# suite must be FIXED, not quarantined. When the baseline carries no quarantine file
# yet (this leg's introduction), there is nothing to ratchet against and only the
# checks above apply — the state is printed either way, never silently skipped.
#   QUARANTINE_BASELINE_REF   git ref to diff against     (default origin/main)
#   QUARANTINE_BASELINE_FILE  read the baseline from a file (local red/green proofs)
BASELINE_REF="${QUARANTINE_BASELINE_REF:-origin/main}"
BASELINE_JSON=""
if [ -n "${QUARANTINE_BASELINE_FILE:-}" ]; then
  [ -f "$QUARANTINE_BASELINE_FILE" ] && BASELINE_JSON="$(cat "$QUARANTINE_BASELINE_FILE")"
else
  # Shallow PR checkouts don't carry origin/main; fetch it best-effort before reading.
  if ! git cat-file -e "$BASELINE_REF:.github/app-ci/quarantine.json" 2>/dev/null; then
    git fetch --no-tags --depth=1 origin main >/dev/null 2>&1 || true
  fi
  BASELINE_JSON="$(git show "$BASELINE_REF:.github/app-ci/quarantine.json" 2>/dev/null || true)"
fi

if [ -n "$BASELINE_JSON" ]; then
  BASELINE_TMP="$(mktemp)"; printf '%s' "$BASELINE_JSON" > "$BASELINE_TMP"
  node -e '
    const fs=require("fs");
    const cur =JSON.parse(fs.readFileSync(process.argv[1],"utf8"));
    const base=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
    const curKeys =new Set(Object.keys(cur.apps ||{}));
    const baseKeys=new Set(Object.keys(base.apps||{}));
    const added=[...curKeys].filter(k=>!baseKeys.has(k));
    const problems=[];
    if (Number(cur.ceiling) > Number(base.ceiling))
      problems.push("ceiling raised "+base.ceiling+" -> "+cur.ceiling);
    if (added.length) problems.push("new quarantined app(s): "+added.join(", "));
    if (problems.length){ process.stderr.write(problems.join("; ")); process.exit(7); }
  ' "$QUARANTINE_FILE" "$BASELINE_TMP"
  ratchet_rc=$?
  rm -f "$BASELINE_TMP"
  if [ "$ratchet_rc" -ne 0 ]; then
    echo "FATAL: the quarantine ratchet only shrinks vs $BASELINE_REF, but this change"
    echo "       widens it (reason above). Raising the ceiling or adding an app is refused"
    echo "       mechanically: a newly-failing suite must be FIXED, not quarantined."
    exit 1
  fi
  echo "quarantine ratchet: OK vs $BASELINE_REF (ceiling not raised, no new apps)."
else
  echo "quarantine ratchet: no baseline quarantine at $BASELINE_REF (introduction); len<=ceiling only."
fi

# Invariant 3: no stale quarantine entries.
for qa in "${Q_APPS[@]}"; do
  qpj="apps/$qa/package.json"
  if [ ! -f "$qpj" ]; then
    echo "FATAL: quarantined app '$qa' no longer exists ($qpj is missing)."
    echo "       Remove it from $QUARANTINE_FILE AND lower the ceiling."
    exit 1
  fi
  qscript="$(read_test_script "$qpj")"; qrc=$?
  if [ "$qrc" -ne 0 ]; then
    echo "FATAL: quarantined app '$qa' has an unreadable/unparseable $qpj."
    echo "       A broken quarantined app must be fixed, not waved through."
    exit 1
  fi
  if [ -z "$qscript" ]; then
    echo "FATAL: quarantined app '$qa' no longer declares a test script."
    echo "       Remove it from $QUARANTINE_FILE AND lower the ceiling."
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# 3. Report every bucket loudly. Nothing is skipped without a name.
# ---------------------------------------------------------------------------
echo "== node-app-suites =="
echo "node --test apps discovered (${#NODE_APPS[@]}): ${NODE_APPS[*]}"
echo "quarantined (named, ceiling=$CEILING, shrink-only) (${#Q_APPS[@]}): ${Q_APPS[*]:-<none>}"
if [ "${#OTHER_APPS[@]}" -gt 0 ]; then
  echo "other-harness apps with a test script — NOT run by this leg, reported for the record:"
  printf '  - %s\n' "${OTHER_APPS[@]}"
fi

# ---------------------------------------------------------------------------
# 4. Compute the run set = node apps minus quarantine; something must remain.
# ---------------------------------------------------------------------------
RUN=()
for a in "${NODE_APPS[@]}"; do
  skip=0
  for q in "${Q_APPS[@]}"; do [ "$a" = "$q" ] && skip=1 && break; done
  [ "$skip" -eq 0 ] && RUN+=("$a")
done

# Invariant 4: a fully-quarantined leg that always passes is a failure.
if [ "${#RUN[@]}" -eq 0 ]; then
  echo "FATAL: every discovered node --test app is quarantined; this leg would pass"
  echo "       without running a single suite. Refusing."
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. Run each app under a HARD timeout. exit 124 (a hang) is a FAILURE, not a hang.
# ---------------------------------------------------------------------------
echo "running ${#RUN[@]} app(s) under a ${PER_APP_TIMEOUT}s per-app hard timeout: ${RUN[*]}"
fails=0
for a in "${RUN[@]}"; do
  echo "::group::node-app-suites: $a"
  (
    set -e
    cd "apps/$a"
    # Match the app image's install (npm install --no-audit --no-fund), so a lockfile
    # drift does not paint this coverage leg red for the wrong reason.
    npm install --no-audit --no-fund
    timeout "$PER_APP_TIMEOUT" npm test
  )
  code=$?
  echo "::endgroup::"
  if [ "$code" -eq 124 ]; then
    echo "FAIL[$a]: HANG — killed at ${PER_APP_TIMEOUT}s (exit 124). A suite that cannot exit is RED."
    fails=$((fails + 1))
  elif [ "$code" -ne 0 ]; then
    echo "FAIL[$a]: exit $code"
    fails=$((fails + 1))
  else
    echo "PASS[$a]"
  fi
done

if [ "$fails" -gt 0 ]; then
  echo "RESULT: FAIL — $fails of ${#RUN[@]} run app suite(s) failed."
  exit 1
fi
echo "RESULT: PASS — all ${#RUN[@]} run app suite(s) green; ${#Q_APPS[@]} quarantined (<= ceiling $CEILING)."
