#!/usr/bin/env bash
# End-to-end SEAM smoke for the WordOps lease fabric.
#
# The unit tests each mock the OTHER services. This smoke proves the SEAM: it builds
# the four REAL binaries + a fake homeserver, wires them together over HTTP exactly
# as they are wired in-cluster, and drives a real incident-containment flow —
#
#   broker mints an A4 lease  →  gateway verifies the signed lease  →  the containment engine
#   severs  →  an ExecutionReceipt actually lands in the ledger  →  room-factory opens
#   a governed room
#
# plus a LIVE spoof-block check (a hand-crafted lease is rejected 401). Exit 0 = the
# seam holds; non-zero = a real integration break a unit test could never see.
#
# No cluster, no Docker: just Go + openssl + python3. Runs anywhere.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
BIN="$WORK/bin"; mkdir -p "$BIN"
PIDS=()
PASS=0; FAIL=0

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
info()  { printf '\033[0;36m'; printf '%b' "$*"; printf '\033[0m\n'; }
ok()   { green "  PASS  $1"; PASS=$((PASS+1)); }
fail() { red   "  FAIL  $1"; FAIL=$((FAIL+1)); }

cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" >/dev/null 2>&1 || true; done
  rm -rf "$WORK"
}
trap cleanup EXIT

# jval <json> <python-expression-over-`d`>  — extract a field with python3 (portable; no jq).
jval() { python3 -c 'import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$2" <<<"$1" 2>/dev/null; }

wait_health() { # wait_health <url> <name>
  for _ in $(seq 1 50); do
    if curl -fsS "$1/healthz" >/dev/null 2>&1; then return 0; fi
    sleep 0.2
  done
  fail "$2 did not become healthy at $1"; return 1
}

# ── ports ───────────────────────────────────────────────────────────────────
BROKER=18091 LEDGER=18092 CONT=18093 GW=18094 RF=18095 SYN=18096

info "[build] compiling the four real binaries"
for svc in wordops-capability-broker agent-activity-ledger wordops-mcp-gateway wordops-room-factory; do
  if ( cd "$ROOT/apps/$svc" && GOWORK=off go build -ldflags="-B gobuildid" -o "$BIN/$svc" . ) 2>"$WORK/build.$svc.log"; then
    ok "built $svc"
  else
    fail "build $svc failed"; sed 's/^/    /' "$WORK/build.$svc.log"; exit 1
  fi
done

# ── fake homeserver for the room-factory (returns a room_id for createRoom) ──
cat > "$WORK/fakesyn.py" <<'PY'
import json,sys
from http.server import BaseHTTPRequestHandler,HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length','0') or 0))
        body=json.dumps({"room_id":"!smoke:ops.socioprophet.ai"}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*a): pass
HTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
PY

# ── fake containment endpoint (the real one is gbrg-engine, a Rust service in the
# sociosphere repo — out of this Go+bash smoke's build scope). Returns a PROVED
# ContainmentProofArtifact so the gateway maps it to verdict=verified. Containment
# CORRECTNESS is covered by gbrg-engine's own tests + the Rust golden conformance;
# this smoke proves the LEASE seam, not the sever algorithm. ──
cat > "$WORK/fakecont.py" <<'PY'
import json,sys
from http.server import BaseHTTPRequestHandler,HTTPServer
ART=json.dumps({"schemaVersion":"0.1.0","source":"vvv-648e9d56f1a","severedScope":"full","epistemicLevel":"empirical","status":"PROVED","baselineReachableCount":5,"residualReachableCount":1,"containedCount":4,"residualReachable":["edr-epp"]}).encode()
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b=b'{"status":"ok"}' if self.path.startswith("/healthz") else ART
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self,*a): pass
HTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
PY

info "\n[boot] starting broker, ledger, containment (gbrg-engine stub), gateway, room-factory + fake homeserver"
BROKER_KEY="$WORK/broker.pem"; openssl genrsa -out "$BROKER_KEY" 2048 2>/dev/null
BROKER_ISSUER="https://auth.socioprophet.ai/realms/wordops/wordops-capability-broker"

python3 "$WORK/fakesyn.py" "$SYN" & PIDS+=($!)
WORDOPS_BROKER_SIGNING_KEY="$(cat "$BROKER_KEY")" PORT=$BROKER "$BIN/wordops-capability-broker" >"$WORK/broker.log" 2>&1 & PIDS+=($!)
PORT=$LEDGER "$BIN/agent-activity-ledger" >"$WORK/ledger.log" 2>&1 & PIDS+=($!)
python3 "$WORK/fakecont.py" "$CONT" & PIDS+=($!)
PORT=$GW GBRG_CONTAINMENT_URL="http://127.0.0.1:$CONT" LEDGER_URL="http://127.0.0.1:$LEDGER" \
  BROKER_JWKS_URL="http://127.0.0.1:$BROKER/.well-known/jwks.json" BROKER_ISSUER="$BROKER_ISSUER" \
  "$BIN/wordops-mcp-gateway" >"$WORK/gw.log" 2>&1 & PIDS+=($!)
PORT=$RF MATRIX_HS_URL="http://127.0.0.1:$SYN" MATRIX_ACCESS_TOKEN="fake-smoke-token-not-real" \
  "$BIN/wordops-room-factory" >"$WORK/rf.log" 2>&1 & PIDS+=($!)

for h in "http://127.0.0.1:$BROKER broker" "http://127.0.0.1:$LEDGER ledger" "http://127.0.0.1:$CONT containment" "http://127.0.0.1:$GW gateway" "http://127.0.0.1:$RF room-factory"; do
  wait_health $h || exit 1
done
ok "all services healthy"

# ── 1. broker mints an A4 lease ──────────────────────────────────────────────
info "\n[flow] 1. broker issues an A4 containment lease"
ISSUE='{"user":{"id":"user:responder","roles":["responder"]},"agent":{"id":"agent:containment"},
  "request":{"aud":"mcp://gbrg-containment","scope":["containment:sever:full"],"risk_class":"A4",
  "case_id":"CASE-SMOKE-1","task_id":"TASK-1","ttl_seconds":30,"approval_id":"APR-1","step_up_satisfied":true}}'
LEASE_RESP="$(curl -fsS -X POST "http://127.0.0.1:$BROKER/lease" -H 'Content-Type: application/json' -d "$ISSUE")"
TOKEN="$(jval "$LEASE_RESP" 'd["lease_token"]')"
if [ -n "$TOKEN" ] && [ "$(jval "$LEASE_RESP" 'd["issued"]')" = "True" ]; then ok "lease issued (signed JWT)"; else fail "broker did not issue a lease: $LEASE_RESP"; fi

# ── 2. gateway verifies + severs ─────────────────────────────────────────────
info "[flow] 2. gateway verifies the signed lease and severs"
INVOKE=$(python3 -c 'import json,sys; print(json.dumps({"lease_token":sys.argv[1],"tool":{"name":"sever_endpoint","audience":"mcp://gbrg-containment","required_scope":"containment:sever:full"},"params":{"scope":"full"}}))' "$TOKEN")
GW_RESP="$(curl -fsS -X POST "http://127.0.0.1:$GW/mcp/invoke" -H 'Content-Type: application/json' -d "$INVOKE")"
RECEIPT="$(jval "$GW_RESP" 'd["receipt_hash"]')"
if [ "$(jval "$GW_RESP" 'd["admitted"]')" = "True" ] && [ "$(jval "$GW_RESP" 'd["verdict"]')" = "verified" ]; then
  ok "gateway admitted the real lease and returned verdict=verified"
else fail "gateway did not admit a valid lease: $GW_RESP"; fi

# ── 3. the receipt ACTUALLY reached the ledger (the seam) ─────────────────────
info "[flow] 3. the ExecutionReceipt actually landed in the ledger"
LEDGER_RESP="$(curl -fsS "http://127.0.0.1:$LEDGER/executions")"
if [ -n "$RECEIPT" ] && python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if any(r.get("receipt_hash")==sys.argv[1] for r in d["receipts"]) else 1)' "$RECEIPT" <<<"$LEDGER_RESP"; then
  ok "receipt $RECEIPT is present in the ledger (gateway→ledger seam holds)"
else fail "gateway's receipt did NOT reach the ledger"; fi

# ── 4. LIVE spoof-block: a hand-crafted lease is rejected ────────────────────
info "[flow] 4. spoof-block — a self-made (unsigned) lease is rejected live"
# Build the forged token at runtime so no JWT-looking literal sits in the repo: a
# valid-looking header/payload with a bogus signature — what an attacker would try.
b64url() { base64 | tr '+/' '-_' | tr -d '='; }
FORGED="$(printf '%s' '{"alg":"RS256","typ":"JWT"}' | b64url).$(printf '%s' '{"sub":"attacker"}' | b64url).clearly-invalid"
SPOOF="$(python3 -c 'import json,sys; print(json.dumps({"lease_token":sys.argv[1],"tool":{"name":"sever_endpoint","audience":"mcp://gbrg-containment","required_scope":"containment:sever:full"},"params":{"scope":"full"}}))' "$FORGED")"
CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$GW/mcp/invoke" -H 'Content-Type: application/json' -d "$SPOOF")"
if [ "$CODE" = "401" ]; then ok "forged lease rejected 401 (spoofable-gap stays closed under real services)"; else fail "forged lease was NOT rejected (got $CODE)"; fi

# ── 5. room-factory opens a governed room ────────────────────────────────────
info "[flow] 5. room-factory opens a governed incident room"
RF_RESP="$(curl -fsS -X POST "http://127.0.0.1:$RF/rooms" -H 'Content-Type: application/json' -d '{"type":"incident","ref":"SMOKE-1","invitees":["@ic:ops.socioprophet.ai"]}')"
if [ "$(jval "$RF_RESP" 'd["encrypted"]')" = "True" ] && [ "$(jval "$RF_RESP" 'd["federated"]')" = "False" ] && [ -n "$(jval "$RF_RESP" 'd["room_id"]')" ]; then
  ok "governed room created (encrypted, non-federated)"
else fail "room-factory did not open a governed room: $RF_RESP"; fi

# ── verdict ──────────────────────────────────────────────────────────────────
echo ""
info "[result] $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then red "SEAM SMOKE FAILED"; exit 1; fi
green "SEAM SMOKE PASSED — the WordOps lease fabric holds end-to-end"
