#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
required=(
  "$ROOT/docs/CLOUDSHELL_FOG_RELEASE_EVIDENCE_V0.md"
  "$ROOT/docs/FOGSTACK_SIGNED_MANIFESTS.md"
  "$ROOT/contracts/cloudshell-fog/compatibility-statement-v0.json"
  "$ROOT/apps/cloudshell-fog/component-version-manifest.example.yaml"
  "$ROOT/releases/manifests/fogstack.access-cloudshell-fog.example.manifest.json"
  "$ROOT/tools/attach_fogstack_manifest_signature.py"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog release evidence assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog release evidence assets present"
