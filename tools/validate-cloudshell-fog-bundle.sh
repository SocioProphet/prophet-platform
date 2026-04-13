#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
required=(
  "$ROOT/docs/CLOUDSHELL_FOG_RUNTIME_V2_GUIDE.md"
  "$ROOT/docs/CLOUDSHELL_FOG_SECRETS_AND_IMAGES_V0.md"
  "$ROOT/infra/argocd/cloudshell-fog-policy-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-runtime-v2-standard-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-runtime-v2-federal-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-stack-standard-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-stack-federal-application.yaml"
  "$ROOT/contracts/cloudshell-fog/deployment-inventory-v0.json"
  "$ROOT/apps/cloudshell-fog/deployment-inventory.standard.example.yaml"
  "$ROOT/apps/cloudshell-fog/deployment-inventory.federal.example.yaml"
  "$ROOT/infra/k8s/cloudshell-fog/runtime-base/cloudshell-fog-secrets.example.yaml"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog bundle assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog bundle assets present"
