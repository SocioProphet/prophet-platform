#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
required=(
  "$ROOT/docs/CLOUDSHELL_FOG_RUNTIME_V2_GUIDE.md"
  "$ROOT/docs/CLOUDSHELL_FOG_MIGRATION_TO_V2.md"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/runtime-v2-standard/kustomization.yaml"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/runtime-v2-federal/kustomization.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-runtime-v2-standard-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-runtime-v2-federal-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-stack-standard-application.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-stack-federal-application.yaml"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/runtime-default/TRANSITIONAL.md"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/runtime-federal/TRANSITIONAL.md"
  "$ROOT/infra/argocd/cloudshell-fog-runtime-application.TRANSITIONAL.md"
  "$ROOT/infra/argocd/cloudshell-fog-runtime-federal-application.TRANSITIONAL.md"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog v2 canonical path is incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog v2 canonical path assets present"
