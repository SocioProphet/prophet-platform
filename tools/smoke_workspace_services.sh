#!/usr/bin/env bash
# Smoke test for workspace services (requires Docker daemon).
# Brings up the stack, waits for health, probes each service, then tears down.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/infra/local/docker-compose.workspace.yml"
PASS=0
FAIL=0

red()   { echo -e "\033[0;31m$*\033[0m"; }
green() { echo -e "\033[0;32m$*\033[0m"; }
info()  { echo -e "\033[0;36m$*\033[0m"; }

ok()   { green "  PASS  $1"; ((PASS++)); }
fail() { red   "  FAIL  $1"; ((FAIL++)); }

# ── Preflight ─────────────────────────────────────────────────────────────────
info "\n[preflight]"

if ! command -v docker &>/dev/null; then
  fail "docker not found in PATH"
  exit 1
fi
ok "docker binary found"

if ! docker info &>/dev/null 2>&1; then
  fail "Docker daemon is not running. Start Docker Desktop or the Docker daemon and retry."
  exit 1
fi
ok "docker daemon is running"

if ! command -v docker &>/dev/null || ! docker compose version &>/dev/null 2>&1; then
  fail "docker compose plugin not available"
  exit 1
fi
ok "docker compose available"

# Check required ports are free before binding
for port in 143 25 587 5232 9000 5432 6379; do
  if lsof -iTCP:"$port" -sTCP:LISTEN -n -P &>/dev/null 2>&1; then
    fail "port $port already in use — stop conflicting process before running smoke test"
    exit 1
  fi
  ok "port $port is free"
done

# ── Build ─────────────────────────────────────────────────────────────────────
info "\n[build]"
docker compose -f "$COMPOSE_FILE" build --quiet
ok "docker compose build succeeded"

# ── Up ────────────────────────────────────────────────────────────────────────
info "\n[up]"

cleanup() {
  info "\n[teardown]"
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans &>/dev/null
  ok "stack torn down"
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" up -d
ok "docker compose up -d succeeded"

# ── Wait for services ──────────────────────────────────────────────────────────
info "\n[waiting for services]"

wait_tcp() {
  local name="$1" host="$2" port="$3" max_secs="${4:-30}"
  local elapsed=0
  while ! nc -z "$host" "$port" &>/dev/null 2>&1; do
    sleep 2; elapsed=$((elapsed+2))
    if [ $elapsed -ge $max_secs ]; then
      fail "$name: timed out after ${max_secs}s waiting for $host:$port"
      return 1
    fi
  done
  ok "$name: $host:$port open after ${elapsed}s"
}

wait_http() {
  local name="$1" url="$2" max_secs="${3:-30}"
  local elapsed=0
  while ! curl -sf --max-time 3 "$url" &>/dev/null 2>&1; do
    sleep 2; elapsed=$((elapsed+2))
    if [ $elapsed -ge $max_secs ]; then
      fail "$name: timed out after ${max_secs}s waiting for $url"
      return 1
    fi
  done
  ok "$name: $url responded after ${elapsed}s"
}

wait_tcp  "postgres"        127.0.0.1  5432  45
wait_tcp  "redis"           127.0.0.1  6379  30
wait_tcp  "dovecot-imap"    127.0.0.1  143   45
wait_tcp  "postfix-smtp"    127.0.0.1  25    45
wait_http "minio-health"    "http://127.0.0.1:9000/minio/health/ready" 60
wait_http "caldav"          "http://127.0.0.1:5232/.well-known/caldav" 45

# ── IMAP banner probe ──────────────────────────────────────────────────────────
info "\n[imap banner]"
banner=$(echo -e "A1 LOGOUT\r" | nc -w 3 127.0.0.1 143 2>/dev/null || true)
if echo "$banner" | grep -qi "IMAP\|Dovecot\|OK"; then
  ok "IMAP banner received"
else
  fail "IMAP banner not received (got: ${banner:0:80})"
fi

# ── CalDAV well-known redirect ─────────────────────────────────────────────────
info "\n[caldav well-known]"
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:5232/.well-known/caldav" 2>/dev/null || true)
if [[ "$status" == "302" || "$status" == "301" || "$status" == "200" ]]; then
  ok "CalDAV well-known returned HTTP $status"
else
  fail "CalDAV well-known returned HTTP $status (expected 2xx/3xx)"
fi

# ── MinIO console ─────────────────────────────────────────────────────────────
info "\n[minio]"
minio_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:9001" 2>/dev/null || true)
if [[ "$minio_status" == "200" || "$minio_status" == "302" ]]; then
  ok "MinIO console returned HTTP $minio_status"
else
  fail "MinIO console returned HTTP $minio_status"
fi

# ── Redis PING ────────────────────────────────────────────────────────────────
info "\n[redis]"
pong=$(docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping 2>/dev/null || true)
if echo "$pong" | grep -q "PONG"; then
  ok "Redis PING → PONG"
else
  fail "Redis PING did not return PONG (got: $pong)"
fi

# ── PostgreSQL workspace tables ───────────────────────────────────────────────
info "\n[postgres workspace tables]"
tables=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U prophet -d prophet_platform -tc \
  "SELECT tablename FROM pg_tables WHERE tablename IN ('mail_domains','mail_users');" \
  2>/dev/null | tr -d ' ' | grep -v '^$' || true)
for table in mail_domains mail_users; do
  if echo "$tables" | grep -q "$table"; then
    ok "postgres table '$table' exists"
  else
    fail "postgres table '$table' not found (migration may not have run)"
  fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "========================="
echo "Workspace smoke test done"
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "========================="

[ "$FAIL" -eq 0 ]
