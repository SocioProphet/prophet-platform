#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TARGETS=(
  "$ROOT/infra/k8s/cloudshell-fog/runtime-base/deployment.yaml"
  "$ROOT/infra/k8s/cloudshell-fog/overlays/runtime-v2-federal/profile-configmap-patch.yaml"
  "$ROOT/apps/cloudshell-fog/deployment-inventory.standard.example.yaml"
  "$ROOT/apps/cloudshell-fog/deployment-inventory.federal.example.yaml"
  "$ROOT/infra/policy/cloudshell-fog/kyverno/verify-signed-images.yaml"
)

PLACEHOLDERS=(
  "REPLACE_WITH_PINNED_DIGEST"
  "REPLACE_WITH_REAL_DIGEST"
  "REPLACE_WITH_REAL_COSIGN_PUBLIC_KEY"
  "REPLACE_WITH_SECRET_MANAGER_OR_EXTERNAL_SECRET"
  "REPLACE_WITH_FEDERAL_FALLBACK_REGION"
  "REPLACE_WITH_OIDC_ISSUER"
)

found=0
for file in "${TARGETS[@]}"; do
  [[ -f "$file" ]] || continue
  for token in "${PLACEHOLDERS[@]}"; do
    if grep -q "$token" "$file"; then
      echo "PLACEHOLDER: $token in $file" >&2
      found=1
    fi
  done
done

if [[ $found -ne 0 ]]; then
  echo "cloudshell-fog still contains unresolved production placeholders" >&2
  exit 1
fi

echo "OK: no tracked cloudshell-fog production placeholders detected"
