#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

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

echo "OK: cloudshell-fog structural conformance passed"
