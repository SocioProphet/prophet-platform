#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
required=(
  "$ROOT/docs/CLOUDSHELL_FOG_RUNTIME_GOVERNANCE_BINDING_V0.md"
  "$ROOT/contracts/cloudshell-fog/runtime-governance-binding-v0.json"
  "$ROOT/docs/CLOUDSHELL_FOG_RELEASE_EVIDENCE_V0.md"
  "$ROOT/docs/FOGSTACK_SIGNED_MANIFESTS.md"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog runtime governance binding assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog runtime governance binding assets present"
