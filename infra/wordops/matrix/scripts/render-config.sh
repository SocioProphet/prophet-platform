#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

: "${WORDOPS_PUBLIC_SERVER_NAME:=wordops-public.localhost}"
: "${WORDOPS_PRIVATE_SERVER_NAME:=wordops-private.localhost}"
: "${WORDOPS_PUBLIC_BASE_URL:=http://localhost:8008}"
: "${WORDOPS_PRIVATE_BASE_URL:=http://localhost:8018}"
: "${WORDOPS_PUBLIC_DB_NAME:=synapse_public}"
: "${WORDOPS_PUBLIC_DB_USER:=synapse_public}"
: "${WORDOPS_PUBLIC_DB_PASSWORD:=change-public-db-password}"
: "${WORDOPS_PRIVATE_DB_NAME:=synapse_private}"
: "${WORDOPS_PRIVATE_DB_USER:=synapse_private}"
: "${WORDOPS_PRIVATE_DB_PASSWORD:=change-private-db-password}"
: "${WORDOPS_PUBLIC_ENABLE_REGISTRATION:=false}"
: "${WORDOPS_PRIVATE_ENABLE_REGISTRATION:=false}"

export WORDOPS_PUBLIC_SERVER_NAME WORDOPS_PRIVATE_SERVER_NAME
export WORDOPS_PUBLIC_BASE_URL WORDOPS_PRIVATE_BASE_URL
export WORDOPS_PUBLIC_DB_NAME WORDOPS_PUBLIC_DB_USER WORDOPS_PUBLIC_DB_PASSWORD
export WORDOPS_PRIVATE_DB_NAME WORDOPS_PRIVATE_DB_USER WORDOPS_PRIVATE_DB_PASSWORD
export WORDOPS_PUBLIC_ENABLE_REGISTRATION WORDOPS_PRIVATE_ENABLE_REGISTRATION

mkdir -p "${ROOT_DIR}/public" "${ROOT_DIR}/private"

envsubst < "${ROOT_DIR}/templates/public-homeserver.yaml.tpl" > "${ROOT_DIR}/public/homeserver.yaml"
envsubst < "${ROOT_DIR}/templates/private-homeserver.yaml.tpl" > "${ROOT_DIR}/private/homeserver.yaml"

cat > "${ROOT_DIR}/public/log.config" <<'YAML'
version: 1
formatters:
  precise:
    format: '%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: precise
loggers:
  synapse:
    level: INFO
root:
  level: INFO
  handlers: [console]
YAML

cp "${ROOT_DIR}/public/log.config" "${ROOT_DIR}/private/log.config"

echo "Rendered WordOps Matrix Synapse configs under ${ROOT_DIR}/public and ${ROOT_DIR}/private"
