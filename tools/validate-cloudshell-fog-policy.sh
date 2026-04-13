#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

required=(
  "$ROOT/infra/policy/cloudshell-fog/kyverno/require-image-digest.yaml"
  "$ROOT/infra/policy/cloudshell-fog/kyverno/verify-signed-images.yaml"
  "$ROOT/infra/policy/cloudshell-fog/kyverno/runtime-baseline.yaml"
  "$ROOT/infra/policy/cloudshell-fog/kyverno/kustomization.yaml"
  "$ROOT/infra/argocd/cloudshell-fog-policy-application.yaml"
)

missing=0
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "cloudshell-fog policy assets are incomplete" >&2
  exit 1
fi

echo "OK: cloudshell-fog policy assets present"
