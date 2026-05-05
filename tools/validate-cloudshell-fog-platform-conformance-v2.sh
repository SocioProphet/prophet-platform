#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <standard|federal>" >&2
  exit 2
fi

PROFILE="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$PROFILE" in
  standard|federal) ;;
  *)
    echo "ERROR: profile must be 'standard' or 'federal'" >&2
    exit 2
    ;;
esac

validators=(
  "$ROOT/tools/validate-cloudshell-fog-v2-path.sh"
  "$ROOT/tools/validate-cloudshell-fog-policy.sh"
  "$ROOT/tools/validate-cloudshell-fog-inventory.sh"
  "$ROOT/tools/validate-cloudshell-fog-decision-records.sh"
  "$ROOT/tools/validate-cloudshell-fog-release-evidence.sh"
  "$ROOT/tools/validate-cloudshell-fog-access-profile.sh"
  "$ROOT/tools/validate-cloudshell-fog-runtime-governance.sh"
  "$ROOT/tools/validate-cloudshell-fog-fogstack-conformance.sh"
  "$ROOT/tools/validate-cloudshell-fog-upstream-alignment.sh"
)

for v in "${validators[@]}"; do
  if [[ ! -f "$v" ]]; then
    echo "ERROR: validator missing: $v" >&2
    exit 1
  fi
  echo "== running $(basename "$v") =="
  bash "$v"
done

bash "$ROOT/tools/validate-cloudshell-fog-go-live-v2.sh" "$PROFILE"

echo "OK: cloudshell-fog platform conformance v2 passed for $PROFILE"
