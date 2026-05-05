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

DECISION_RECORD="$ROOT/apps/cloudshell-fog/production-decision-record.${PROFILE}.yaml"

if [[ ! -f "$DECISION_RECORD" ]]; then
  echo "ERROR: missing production decision record: $DECISION_RECORD" >&2
  echo "Copy the matching .example.yaml file and replace all placeholders first." >&2
  exit 1
fi

validators=(
  "$ROOT/tools/validate-cloudshell-fog-policy.sh"
  "$ROOT/tools/validate-cloudshell-fog-inventory.sh"
  "$ROOT/tools/validate-cloudshell-fog-bundle.sh"
  "$ROOT/tools/validate-cloudshell-fog-placeholders.sh"
  "$ROOT/tools/validate-cloudshell-fog-decision-records.sh"
)

for v in "${validators[@]}"; do
  if [[ ! -f "$v" ]]; then
    echo "ERROR: validator missing: $v" >&2
    exit 1
  fi
  echo "== running $(basename "$v") =="
  bash "$v"
done

if grep -q 'REPLACE_WITH_' "$DECISION_RECORD"; then
  echo "ERROR: unresolved placeholders remain in $DECISION_RECORD" >&2
  exit 1
fi

echo "OK: cloudshell-fog $PROFILE go-live v2 gate passed"
