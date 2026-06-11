#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

python -m app.cli serve --host "$HOST" --port "$PORT"
