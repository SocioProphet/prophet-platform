#!/usr/bin/env sh
set -eu

EDGE_BASE="${WORDOPS_MATRIX_EDGE_BASE_URL:-http://localhost:8088}"
PUBLIC_BASE="${WORDOPS_PUBLIC_BASE_URL:-http://localhost:8008}"
PRIVATE_BASE="${WORDOPS_PRIVATE_BASE_URL:-http://localhost:8018}"

check_url() {
  label="$1"
  url="$2"
  echo "Checking ${label}: ${url}"
  curl -fsS "$url" >/dev/null
}

check_url "public client versions" "${PUBLIC_BASE}/_matrix/client/versions"
check_url "private client versions" "${PRIVATE_BASE}/_matrix/client/versions"
check_url "edge health" "${EDGE_BASE}/healthz"
check_url "client well-known" "${EDGE_BASE}/.well-known/matrix/client"
check_url "support well-known" "${EDGE_BASE}/.well-known/matrix/support"

echo "WordOps Matrix local smoke checks passed."
