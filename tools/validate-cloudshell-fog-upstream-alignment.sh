#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
required=(
  "$ROOT/docs/CLOUDSHELL_FOG_UPSTREAM_VALIDATION_MATRIX_V0.md"
  "$ROOT/contracts/cloudshell-fog/runtime-governance-binding-v0.json"
  "$ROOT/contracts/cloudshell-fog/fogstack-access-profile-v0.json"
  "$ROOT/contracts/cloudshell-fog/compatibility-statement-v0.json"
  "$ROOT/docs/CLOUDSHELL_FOG_RELEASE_EVIDENCE_V0.md"
  "$ROOT/tools/validate-cloudshell-fog-runtime-governance.sh"
  "$ROOT/tools/validate-cloudshell-fog-release-evidence.sh"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog upstream alignment assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog upstream alignment assets present"
