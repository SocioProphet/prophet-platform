#!/bin/bash
set -e

# Validate existence of runtime files and resources
FILES=(
    "infra/k8s/cloudshell-fog/runtime-base/deployment.yaml"
    "infra/k8s/cloudshell-fog/runtime-base/service.yaml"
    "infra/k8s/cloudshell-fog/overlays/runtime-default/kustomization.yaml"
    "infra/k8s/cloudshell-fog/overlays/runtime-federal/kustomization.yaml"
    "infra/argocd/cloudshell-fog-runtime-application.yaml"
    )

for FILE in "${FILES[@]}"; do
  if [[ ! -f "$FILE" ]]; then
    echo "ERROR: $FILE does not exist."
    exit 1
  fi
done

echo "All runtime files are present."
