#!/bin/bash
# Runs once on first container start via foreman-installer-bootstrap.service.
# On subsequent starts systemd brings up foreman/pulp services directly.
set -euo pipefail

MARKER=/var/lib/foreman/.sourceos-initialized
LOG=/var/log/foreman-installer-bootstrap.log

exec > >(tee -a "$LOG") 2>&1

if [ -f "$MARKER" ]; then
    echo "Foreman+Katello already initialized — skipping installer."
    exit 0
fi

echo "=== SourceOS Foreman+Katello bootstrap ==="
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Organization: ${FOREMAN_ORG}"

# Wait for postgres to accept connections (belt-and-suspenders alongside
# compose depends_on health check)
for i in $(seq 1 30); do
    if pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
        echo "Postgres ready."
        break
    fi
    echo "Waiting for postgres (attempt ${i}/30)..."
    sleep 5
done

foreman-installer \
    --scenario katello \
    --no-enable-puppet \
    --no-enable-foreman-plugin-puppet \
    --foreman-initial-organization="${FOREMAN_ORG}" \
    --foreman-initial-location="${FOREMAN_LOCATION}" \
    --foreman-initial-admin-username="${FOREMAN_ADMIN_USER}" \
    --foreman-initial-admin-password="${FOREMAN_ADMIN_PASSWORD}" \
    --foreman-db-manage=false \
    --foreman-db-host="${POSTGRES_HOST}" \
    --foreman-db-port="${POSTGRES_PORT}" \
    --foreman-db-database="${POSTGRES_DB}" \
    --foreman-db-username="${POSTGRES_USER}" \
    --foreman-db-password="${POSTGRES_PASSWORD}" \
    --katello-candlepin-db-host="${POSTGRES_HOST}" \
    --katello-candlepin-db-name=candlepin \
    --katello-candlepin-db-user="${POSTGRES_USER}" \
    --katello-candlepin-db-password="${POSTGRES_PASSWORD}" \
    --pulpcore-cache-enabled=true \
    --pulpcore-cache-url="redis://${REDIS_HOST}:${REDIS_PORT}" \
    --foreman-foreman-url="https://127.0.0.1"

touch "$MARKER"
echo "Bootstrap complete: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Access: https://127.0.0.1:8443"
echo "Credentials: ${FOREMAN_ADMIN_USER} / <FOREMAN_ADMIN_PASSWORD>"
