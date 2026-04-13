#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="$ROOT/infra/local/docker-compose.evidence-receipts.yml"
STATE_ROOT="/tmp/prophet-platform-state"
TMPDIR="$(mktemp -d)"
trap 'docker compose -f "$COMPOSE" down -v >/dev/null 2>&1 || true; rm -rf "$TMPDIR" "$STATE_ROOT"' EXIT

mkdir -p "$STATE_ROOT/prophet-platform/payloads/eval-fabric-api"
mkdir -p "$STATE_ROOT/prophet-platform/events/eval-fabric-api"
mkdir -p "$STATE_ROOT/prophet-platform/receipts/eval-fabric-api"
mkdir -p "$STATE_ROOT/prophet-platform/catalog/lampstand"
mkdir -p "$STATE_ROOT/prophet-platform/payloads/lampstand"
mkdir -p "$STATE_ROOT/prophet-platform/events/lampstand"
mkdir -p "$STATE_ROOT/prophet-platform/receipts/lampstand"

cat > "$STATE_ROOT/prophet-platform/payloads/eval-fabric-api/corr-ef.payload.json" <<'EOF'
{"profile_id":"profile.high_assurance_enterprise_agent"}
EOF
cat > "$STATE_ROOT/prophet-platform/events/eval-fabric-api/corr-ef.event.json" <<EOF
{"event_type":"eval.fabric.frontier.read","payload_ref":"file://$STATE_ROOT/prophet-platform/payloads/eval-fabric-api/corr-ef.payload.json","created_at":"2026-04-13T00:00:00+00:00"}
EOF
cat > "$STATE_ROOT/prophet-platform/receipts/eval-fabric-api/corr-ef.receipt.json" <<'EOF'
{"status":"succeeded","action":"FrontierQuery","subject_ref":"profile://profile.high_assurance_enterprise_agent","created_at":"2026-04-13T00:00:00+00:00"}
EOF

cat > "$STATE_ROOT/prophet-platform/payloads/lampstand/lamp-1.CarrierIngested.json" <<'EOF'
{"carrier_ref":"carrier://sha256/abc"}
EOF
cat > "$STATE_ROOT/prophet-platform/events/lampstand/lamp-1.event.json" <<'EOF'
{"event_type":"carrier.ingested","created_at":"2026-04-13T00:00:00+00:00"}
EOF
cat > "$STATE_ROOT/prophet-platform/receipts/lampstand/lamp-1.receipt.json" <<'EOF'
{"status":"succeeded","action":"CarrierIngest","subject_ref":"carrier://sha256/abc"}
EOF
cat > "$STATE_ROOT/prophet-platform/catalog/lampstand/receipt_catalog.jsonl" <<EOF
{"correlation_id":"lamp-1","payload_ref":"file://$STATE_ROOT/prophet-platform/payloads/lampstand/lamp-1.CarrierIngested.json","event_ref":"file://$STATE_ROOT/prophet-platform/events/lampstand/lamp-1.event.json","receipt_ref":"file://$STATE_ROOT/prophet-platform/receipts/lampstand/lamp-1.receipt.json"}
EOF

docker compose -f "$COMPOSE" up --build -d

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8088/v1/evidence/services > "$TMPDIR/services.json" 2>/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://127.0.0.1:8088/v1/evidence/receipts/recent?service=eval-fabric-api&limit=5" > "$TMPDIR/eval_recent.json"
curl -fsS "http://127.0.0.1:8088/v1/evidence/receipts/eval-fabric-api/corr-ef" > "$TMPDIR/eval_bundle.json"
curl -fsS "http://127.0.0.1:8088/v1/evidence/catalog/recent?service=lampstand&limit=5" > "$TMPDIR/lamp_catalog.json"

python3 - "$TMPDIR" <<'PY'
import json
import sys
from pathlib import Path

tmp = Path(sys.argv[1])
services = json.loads((tmp / "services.json").read_text())
eval_recent = json.loads((tmp / "eval_recent.json").read_text())
eval_bundle = json.loads((tmp / "eval_bundle.json").read_text())
lamp_catalog = json.loads((tmp / "lamp_catalog.json").read_text())

assert "eval-fabric-api" in services["services"], services
assert "lampstand" in services["services"], services
assert eval_recent["items"][0]["correlation_id"] == "corr-ef", eval_recent
assert eval_bundle["payload"]["profile_id"] == "profile.high_assurance_enterprise_agent", eval_bundle
assert lamp_catalog["items"][0]["correlation_id"] == "lamp-1", lamp_catalog
print('{"ok": true, "gateway_proxy": true, "reader": true, "layout": "type-first"}')
PY
