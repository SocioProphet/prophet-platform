#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_ADDR="${API_ADDR:-unix:///tmp/prophet-platform-smoke.sock}"
GATEWAY_PORT="${GATEWAY_PORT:-18080}"
export TRITRPC_ALLOW_INSECURE_DEV_KEY=1
export TRITRPC_LISTEN_ADDR="$API_ADDR"
export TRITRPC_TARGET_ADDR="$API_ADDR"
export GATEWAY_PORT

cleanup() {
  kill ${API_PID:-} ${GW_PID:-} 2>/dev/null || true
  rm -f /tmp/prophet-platform-smoke.sock
}
trap cleanup EXIT

(cd "$ROOT" && go run ./apps/api/cmd/socioprophet-api) >/tmp/prophet-platform-api.log 2>&1 &
API_PID=$!

for _ in $(seq 1 30); do
  if [ -S /tmp/prophet-platform-smoke.sock ]; then
    break
  fi
  sleep 0.2
done

(cd "$ROOT" && go run ./apps/gateway/cmd/tritrpc-gateway) >/tmp/prophet-platform-gateway.log 2>&1 &
GW_PID=$!

for _ in $(seq 1 50); do
  if curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/health" >/tmp/prophet-platform-smoke-response.json 2>/dev/null; then
    cat /tmp/prophet-platform-smoke-response.json
    exit 0
  fi
  sleep 0.2
done

echo "gateway never became healthy" >&2
cat /tmp/prophet-platform-api.log >&2 || true
echo '---' >&2
cat /tmp/prophet-platform-gateway.log >&2 || true
exit 1
