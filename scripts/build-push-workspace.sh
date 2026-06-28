#!/usr/bin/env bash
# Build + push the prophet-workspace mail/caldav container images to GHCR.
# Uses podman (preferred) or docker. Requires a GHCR login: echo $CR_PAT | podman login ghcr.io -u <user> --password-stdin
set -euo pipefail
cd "$(dirname "$0")/.."

REG="${REGISTRY:-ghcr.io/socioprophet/prophet-platform}"
TAG="${TAG:-dev}"
ENGINE="$(command -v podman || command -v docker)"; [ -n "$ENGINE" ] || { echo "need podman or docker"; exit 1; }
echo "engine: $ENGINE   registry: $REG   tag: $TAG"

build_push() {  # <svc-dir> <image-name>
  echo "── $2 ──"
  "$ENGINE" build --platform linux/amd64 -t "$REG/$2:$TAG" "services/$1"
  "$ENGINE" push "$REG/$2:$TAG"
}

build_push workspace-smtp   workspace-smtp
build_push workspace-mail   workspace-mail
build_push workspace-caldav workspace-caldav
echo "✓ pushed all three. Deploy: helm upgrade --install prophet-workspace charts/prophet-workspace -n workspace --create-namespace -f <your-values>.yaml"
