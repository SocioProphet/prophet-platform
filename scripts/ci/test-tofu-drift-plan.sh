#!/usr/bin/env bash
#
# Counter-test for scripts/ci/tofu-drift-plan.sh.
#
# Asserts that the three OpenTofu outcomes stay distinguishable, and — the part
# that matters — re-runs the *previous* inline logic against the same stubs to
# show it could not tell them apart. If someone reverts the mapping, the second
# half of this test is what goes red.
#
# `tofu` is stubbed, so this needs no cloud credentials and runs on every PR.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNDER_TEST="${HERE}/tofu-drift-plan.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fails=0
check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then
    printf '  ok    %-52s %s\n' "$1" "$3"
  else
    printf '  FAIL  %-52s expected %s, got %s\n' "$1" "$2" "$3"
    fails=$((fails + 1))
  fi
}

# A stub `tofu`: INIT_EC controls `tofu init`, PLAN_EC controls `tofu plan`.
mkdir -p "${WORK}/bin"
cat > "${WORK}/bin/tofu" <<'STUB'
#!/usr/bin/env bash
case "$1" in
  init) echo "stub: tofu init (exit ${INIT_EC:-0})"; exit "${INIT_EC:-0}" ;;
  plan) echo "stub: tofu plan (exit ${PLAN_EC:-0})"; exit "${PLAN_EC:-0}" ;;
  *)    exit 0 ;;
esac
STUB
chmod +x "${WORK}/bin/tofu"
export PATH="${WORK}/bin:${PATH}"

mkdir -p "${WORK}/lane"

run_new() { # run_new <init_ec> <plan_ec>  -> prints "<script_exit> <drift_output>"
  local out="${WORK}/out.txt"
  : > "$out"
  ( INIT_EC="$1" PLAN_EC="$2" GITHUB_OUTPUT="$out" "$UNDER_TEST" testlane "${WORK}/lane" ) >/dev/null 2>&1
  local ec=$?
  local drift
  drift="$(sed -n 's/^drift=//p' "$out" | tail -1)"
  echo "${ec} ${drift:-<unset>}"
}

# The logic exactly as it stood before this change: plan under
# `continue-on-error: true`, issue opened only when exitcode == '2'.
run_old() { # run_old <init_ec> <plan_ec> -> prints "<job_result> <issue_opened>"
  local out="${WORK}/old.txt"
  : > "$out"
  (
    cd "${WORK}/lane" || exit 1
    set +e
    INIT_EC="$1" tofu init -reconfigure >/dev/null 2>&1
    INIT_EC="$1" PLAN_EC="$2" tofu plan -detailed-exitcode -out=plan.tfplan 2>&1 | tee plan.txt >/dev/null
    ec=${PIPESTATUS[0]}
    set -e
    echo "exitcode=${ec}" >> "$out"
  )
  local step_ec=$?
  # continue-on-error: true meant the job was green whatever the step did.
  local job="green"
  [ "$step_ec" -eq 0 ] || job="green(masked)"
  local captured
  captured="$(sed -n 's/^exitcode=//p' "$out" | tail -1)"
  local issue="no"
  [ "${captured:-}" = "2" ] && issue="yes"
  echo "${job} ${issue}"
}

echo "tofu-drift-plan.sh — exit-code mapping"
check "clean      (init 0, plan 0) -> exit 0, drift=false" "0 false"    "$(run_new 0 0)"
check "drift      (init 0, plan 2) -> exit 0, drift=true"  "0 true"     "$(run_new 0 2)"
check "plan error (init 0, plan 1) -> exit 1, drift=unknown" "1 unknown" "$(run_new 0 1)"
check "init error (init 1)         -> exit 1, drift=unknown" "1 unknown" "$(run_new 1 0)"
check "odd code   (init 0, plan 9) -> exit 1, drift=unknown" "1 unknown" "$(run_new 0 9)"

echo
echo "previous logic on the same stubs — what this change fixes"
check "OLD clean      -> green, no issue"        "green no"  "$(run_old 0 0)"
check "OLD drift      -> green, issue opened"    "green yes" "$(run_old 0 2)"
check "OLD plan error -> green, NO issue"        "green no"  "$(run_old 0 1)"
check "OLD init error -> green, NO issue"        "green no"  "$(run_old 1 0)"

echo
if [ "$fails" -ne 0 ]; then
  echo "FAILED: ${fails} assertion(s)." >&2
  echo "The last two OLD rows are the defect: an error and a clean run produced" >&2
  echo "an identical signal. The first block is what must keep them apart." >&2
  exit 1
fi
echo "PASS: drift, error and clean are distinguishable; the previous logic conflated error with clean."
