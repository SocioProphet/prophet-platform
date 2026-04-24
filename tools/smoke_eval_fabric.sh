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
curl -fsS -D "$TMPDIR/lifecycle.headers" "http://127.0.0.1:8080/v1/models/model.semantic-stack.2026-04-05/lifecycle-bundle" >"$TMPDIR/lifecycle.json"

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
lifecycle = json.loads((tmp / "lifecycle.json").read_text())

def parse_headers(path: Path):
    headers = {}
    for line in path.read_text().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return headers

frontier_headers = parse_headers(tmp / "frontier.headers")
lifecycle_headers = parse_headers(tmp / "lifecycle.headers")

for header_set in (frontier_headers, lifecycle_headers):
    assert header_set.get("x-event-envelope-ref"), header_set
    assert header_set.get("x-evidence-receipt-ref"), header_set
    assert header_set.get("x-payload-ref"), header_set

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

assert lifecycle["model_release_id"] == "model.semantic-stack.2026-04-05", lifecycle
assert lifecycle["agent_ref"].startswith("agent://"), lifecycle
assert lifecycle["recipe_ref"] == "recipe://benchmark/ray/eval-fabric-001", lifecycle
assert lifecycle["promotion_decision"]["target_stage"] == "L4_supervised_actuation", lifecycle
assert lifecycle["rollback_record"]["trigger_ref"] == lifecycle["promotion_decision"]["promotion_decision_id"], lifecycle
assert lifecycle["gate_activation_record"]["action_ref"].endswith("tool_write/logical_route"), lifecycle
assert lifecycle["graduation_record"]["current_stage"] == "L3_assist_mode", lifecycle
assert len(lifecycle["artifact_graph"]["edges"]) == 4, lifecycle

print(frontier_headers["x-payload-ref"])
print(frontier_headers["x-event-envelope-ref"])
print(frontier_headers["x-evidence-receipt-ref"])
print(lifecycle_headers["x-payload-ref"])
print(lifecycle_headers["x-event-envelope-ref"])
print(lifecycle_headers["x-evidence-receipt-ref"])
PY

mapfile -t REFS < "$TMPDIR/refs.txt"
FRONTIER_PAYLOAD_REF="${REFS[0]}"
FRONTIER_EVENT_REF="${REFS[1]}"
FRONTIER_RECEIPT_REF="${REFS[2]}"
LIFECYCLE_PAYLOAD_REF="${REFS[3]}"
LIFECYCLE_EVENT_REF="${REFS[4]}"
LIFECYCLE_RECEIPT_REF="${REFS[5]}"

FRONTIER_PAYLOAD_PATH="${FRONTIER_PAYLOAD_REF#file://}"
FRONTIER_EVENT_PATH="${FRONTIER_EVENT_REF#file://}"
FRONTIER_RECEIPT_PATH="${FRONTIER_RECEIPT_REF#file://}"
LIFECYCLE_PAYLOAD_PATH="${LIFECYCLE_PAYLOAD_REF#file://}"
LIFECYCLE_EVENT_PATH="${LIFECYCLE_EVENT_REF#file://}"
LIFECYCLE_RECEIPT_PATH="${LIFECYCLE_RECEIPT_REF#file://}"

docker compose -f "$COMPOSE" exec -T eval-fabric-api sh -lc "test -f '$FRONTIER_PAYLOAD_PATH' && test -f '$FRONTIER_EVENT_PATH' && test -f '$FRONTIER_RECEIPT_PATH' && test -f '$LIFECYCLE_PAYLOAD_PATH' && test -f '$LIFECYCLE_EVENT_PATH' && test -f '$LIFECYCLE_RECEIPT_PATH'"

for path in "$FRONTIER_PAYLOAD_PATH" "$LIFECYCLE_PAYLOAD_PATH"; do
  case "$path" in
    */payloads/eval-fabric-api/*) ;;
    *) echo "unexpected payload layout: $path" >&2; exit 1 ;;
  esac
done
for path in "$FRONTIER_EVENT_PATH" "$LIFECYCLE_EVENT_PATH"; do
  case "$path" in
    */events/eval-fabric-api/*) ;;
    *) echo "unexpected event layout: $path" >&2; exit 1 ;;
  esac
done
for path in "$FRONTIER_RECEIPT_PATH" "$LIFECYCLE_RECEIPT_PATH"; do
  case "$path" in
    */receipts/eval-fabric-api/*) ;;
    *) echo "unexpected receipt layout: $path" >&2; exit 1 ;;
  esac
done

echo '{"ok":true,"receipts_emitted":true,"layout":"type-first","lifecycle_bundle_verified":true}'
