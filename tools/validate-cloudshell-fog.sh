#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

required=(
  "$ROOT/apps/cloudshell-fog/README.md"
  "$ROOT/infra/k8s/cloudshell-fog/base/kustomization.yaml"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/default/kustomization.yaml"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/federal/kustomization.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-application.yaml"
  "$ROOT/docs/CLOUDSHELL_FOG_INTEGRATION_V0.md"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog platform assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog platform assets present"
