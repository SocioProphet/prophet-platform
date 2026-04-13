#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

validators=(
  "$ROOT/tools/validate-cloudshell-fog-policy.sh"
  "$ROOT/tools/validate-cloudshell-fog-inventory.sh"
  "$ROOT/tools/validate-cloudshell-fog-bundle.sh"
  "$ROOT/tools/validate-cloudshell-fog-placeholders.sh"
)

for v in "${validators[@]}"; do
  if [[ ! -x "$v" ]]; then
    echo "ERROR: validator missing or not executable: $v" >&2
    exit 1
  fi
  echo "== running $(basename "$v") =="
  "$v"
done

echo "OK: cloudshell-fog readiness checks passed"
