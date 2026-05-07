#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

: "${WORDOPS_SYNAPSE_IMAGE:=matrixdotorg/synapse:v1.131.0}"
: "${WORDOPS_PUBLIC_SERVER_NAME:=wordops-public.localhost}"
: "${WORDOPS_PRIVATE_SERVER_NAME:=wordops-private.localhost}"

PUBLIC_KEY="${ROOT_DIR}/public/${WORDOPS_PUBLIC_SERVER_NAME}.signing.key"
PRIVATE_KEY="${ROOT_DIR}/private/${WORDOPS_PRIVATE_SERVER_NAME}.signing.key"

if [ ! -f "${ROOT_DIR}/public/homeserver.yaml" ] || [ ! -f "${ROOT_DIR}/private/homeserver.yaml" ]; then
  echo "homeserver.yaml files are missing; run scripts/render-config.sh first" >&2
  exit 1
fi

if [ ! -f "$PUBLIC_KEY" ]; then
  docker run --rm -v "${ROOT_DIR}/public:/data" "${WORDOPS_SYNAPSE_IMAGE}" \
    generate \
    --server-name "${WORDOPS_PUBLIC_SERVER_NAME}" \
    --config-path /data/homeserver.yaml \
    --generate-keys
fi

if [ ! -f "$PRIVATE_KEY" ]; then
  docker run --rm -v "${ROOT_DIR}/private:/data" "${WORDOPS_SYNAPSE_IMAGE}" \
    generate \
    --server-name "${WORDOPS_PRIVATE_SERVER_NAME}" \
    --config-path /data/homeserver.yaml \
    --generate-keys
fi

echo "WordOps Matrix signing keys are present."
