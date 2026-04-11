#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="$ROOT/infra/local/docker-compose.eval-fabric.yml"
TMPDIR="$(mktemp -d)"

cleanup() {
  docker compose -f "$COMPOSE" down -v >/dev/null 2>&1 || true
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

docker compose -f "$COMPOSE" up --build -d

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8080/healthz" >"$TMPDIR/health.json" 2>/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://127.0.0.1:8080/readyz" >"$TMPDIR/ready.json"
curl -fsS -D "$TMPDIR/frontier.headers" "http://127.0.0.1:8080/v1/frontier" >"$TMPDIR/frontier.json"
curl -fsS "http://127.0.0.1:8080/v1/models/model.semantic-stack.2026-04-05/dossier" >"$TMPDIR/dossier.json"
curl -fsS "http://127.0.0.1:8080/v1/competition/radar" >"$TMPDIR/radar.json"

python3 - "$TMPDIR" <<'PY' > "$TMPDIR/refs.txt"
import json
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
health = json.loads((tmp / "health.json").read_text())
ready = json.loads((tmp / "ready.json").read_text())
frontier = json.loads((tmp / "frontier.json").read_text())
dossier = json.loads((tmp / "dossier.json").read_text())
radar = json.loads((tmp / "radar.json").read_text())

headers = {}
for line in (tmp / "frontier.headers").read_text().splitlines():
    if ":" not in line:
        continue
    k, v = line.split(":", 1)
    headers[k.strip().lower()] = v.strip()

event_ref = headers.get("x-event-envelope-ref")
receipt_ref = headers.get("x-evidence-receipt-ref")
payload_ref = headers.get("x-payload-ref")
assert event_ref and receipt_ref and payload_ref, headers

assert health["status"] == "ok", health
assert health["service"] == "eval-fabric-api", health
assert ready["status"] == "ok", ready
assert ready["postgres"]["ok"] is True, ready
assert ready["clickhouse"]["ok"] is True, ready

subjects = {item["subject_id"]: item for item in frontier["subjects"]}
assert "model.semantic-stack.2026-04-05" in subjects, frontier
assert "gpt5_aug2025" in subjects, frontier
assert subjects["model.semantic-stack.2026-04-05"]["score"] == 0.782, frontier
assert subjects["gpt5_aug2025"]["rank"] == 1, frontier

metric_ids = {item["metric_definition_id"] for item in dossier["metrics"]}
assert "md_denotation_accuracy" in metric_ids, dossier
assert "md_false_allow_rate" in metric_ids, dossier

providers = {item["provider_id"] for item in radar["competitors"]}
assert {"openai", "google"}.issubset(providers), radar

print(payload_ref)
print(event_ref)
print(receipt_ref)
PY

mapfile -t REFS < "$TMPDIR/refs.txt"
PAYLOAD_REF="${REFS[0]}"
EVENT_REF="${REFS[1]}"
RECEIPT_REF="${REFS[2]}"

PAYLOAD_PATH="${PAYLOAD_REF#file://}"
EVENT_PATH="${EVENT_REF#file://}"
RECEIPT_PATH="${RECEIPT_REF#file://}"

docker compose -f "$COMPOSE" exec -T eval-fabric-api sh -lc "test -f '$PAYLOAD_PATH' && test -f '$EVENT_PATH' && test -f '$RECEIPT_PATH'"

echo '{"ok":true,"receipts_emitted":true}'
