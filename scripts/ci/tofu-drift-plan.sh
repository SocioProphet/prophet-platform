#!/usr/bin/env bash
#
# Run `tofu plan -detailed-exitcode` for one cloud lane and map OpenTofu's three
# outcomes onto three DISTINCT CI outcomes.
#
#   tofu exit 0  -> no drift                    -> exit 0, drift=false
#   tofu exit 2  -> drift                       -> exit 0, drift=true   (issue opened)
#   anything else, including a failed `tofu init`
#                -> WE COULD NOT LOOK           -> exit 1, drift=unknown
#
# The third case is the whole point. infra-drift-detect.yml previously ran the
# plan under `continue-on-error: true` and then opened an issue only when
# `exitcode == '2'`. Exit 2 is drift, but exit 1 is *error* -- a failed init,
# expired credentials, an unreachable provider. All of those produced a green
# job and no issue, which is byte-for-byte the same signal as "no drift". The
# estate's only multi-cloud drift detection reported "could not look" as
# "nothing found".
#
# Usage: tofu-drift-plan.sh <lane-name> <working-directory>

set -uo pipefail

LANE="${1:?lane name required}"
DIR="${2:?working directory required}"
OUT="${GITHUB_OUTPUT:-/dev/stdout}"

emit() { printf '%s=%s\n' "$1" "$2" >> "$OUT"; }

fail() {
  echo "::error title=drift check could not run::${LANE}: $1 Drift status is UNKNOWN, not clean." >&2
  emit drift unknown
  exit 1
}

cd "$DIR" || fail "working directory '${DIR}' does not exist."

tofu init -reconfigure 2>&1 | tee init.txt
init_ec="${PIPESTATUS[0]}"
[ "$init_ec" -eq 0 ] || fail "tofu init exited ${init_ec}."

tofu plan -detailed-exitcode -out=plan.tfplan 2>&1 | tee plan.txt
ec="${PIPESTATUS[0]}"
emit exitcode "$ec"

case "$ec" in
  0)
    echo "${LANE}: no drift."
    emit drift false
    ;;
  2)
    echo "::warning title=infrastructure drift::${LANE} has diverged from live state."
    emit drift true
    ;;
  *)
    fail "tofu plan exited ${ec}."
    ;;
esac
