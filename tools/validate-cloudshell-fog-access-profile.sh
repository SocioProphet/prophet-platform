#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
required=(
  "$ROOT/docs/CLOUDSHELL_FOG_ACCESS_PROFILE_V0.md"
  "$ROOT/docs/CLOUDSHELL_FOG_FOGSTACK_ACCESS_BINDING_V0.md"
  "$ROOT/contracts/cloudshell-fog/fogstack-access-profile-v0.json"
  "$ROOT/contracts/cloudshell-fog/compatibility-statement-v0.json"
  "$ROOT/contracts/cloudshell-fog/deployment-inventory-v0.json"
  "$ROOT/contracts/cloudshell-fog/production-decision-record-v0.json"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog access profile assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog access profile assets present"
