#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT/apps/matrix-qes-operator"
TMPDIR="$(mktemp -d)"
PORT="8091"
PID=""

cleanup() {
  if [ -n "$PID" ]; then
    kill "$PID" >/dev/null 2>&1 || true
    wait "$PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

cd "$APP_DIR"
test -d .venv || python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt -r requirements-test.txt >/dev/null

SOCIOPROFIT_STATE_HOME="$TMPDIR" uvicorn app.main:app --port "$PORT" >/dev/null 2>&1 &
PID="$!"

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >"$TMPDIR/health.json" 2>/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS "http://127.0.0.1:${PORT}/v1/matrix-qes/transitions" >"$TMPDIR/transitions.json"
curl -fsS -X POST "http://127.0.0.1:${PORT}/v1/matrix-qes/commands/parse" \
  -H 'content-type: application/json' \
  -d '{"actor":"@ops:example.org","room_id":"!incident:example.org","thread_id":"$thread1","body":"!qes ack"}' >"$TMPDIR/parse.json"
curl -fsS -X POST "http://127.0.0.1:${PORT}/v1/matrix-qes/commands/apply" \
  -H 'content-type: application/json' \
  -d '{"actor":"@ops:example.org","room_id":"!incident:example.org","thread_id":"$thread1","body":"!qes ack"}' >"$TMPDIR/apply1.json"
curl -fsS -X POST "http://127.0.0.1:${PORT}/v1/matrix-qes/commands/apply" \
  -H 'content-type: application/json' \
  -d '{"actor":"@ops:example.org","room_id":"!incident:example.org","thread_id":"$thread1","body":"!qes investigate"}' >"$TMPDIR/apply2.json"

python3 - "$TMPDIR" <<'PY'
import json
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
health = json.loads((tmp / "health.json").read_text())
transitions = json.loads((tmp / "transitions.json").read_text())
parsed = json.loads((tmp / "parse.json").read_text())
apply1 = json.loads((tmp / "apply1.json").read_text())
apply2 = json.loads((tmp / "apply2.json").read_text())

assert health["status"] == "ok", health
assert health["service"] == "matrix-qes-operator", health
assert "triage" in transitions["transitions"], transitions
assert parsed["command"]["verb"] == "ack", parsed
assert apply1["previous_state"] == "triage", apply1
assert apply1["current_state"] == "acknowledged", apply1
assert apply2["previous_state"] == "acknowledged", apply2
assert apply2["current_state"] == "investigating", apply2
print('{"ok":true,"operator_smoke":true}')
PY
