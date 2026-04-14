#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-18080}"
export MCP_STATIC_TOKENS_FILE="${MCP_STATIC_TOKENS_FILE:-config/static_tokens.example.json}"
python server.py serve-http --host 127.0.0.1 --port "$PORT" &
PID=$!
trap 'kill "$PID" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 50); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done
curl -sS -H "Authorization: Bearer reader-token" "http://127.0.0.1:${PORT}/search?q=canonical&limit=2"
