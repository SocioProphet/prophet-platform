#!/usr/bin/env bash
# dev-stack — boot the full local SocioProphet workbench stack in one command.
#
# Stands up every backend the cockpit + Prophet Studio surfaces need, so demos stop
# 502-ing on missing services. Idempotent: a service already listening on its port is
# left alone. Backends run detached (nohup) with logs under scripts/.dev-logs/.
#
#   ./scripts/dev-stack.sh          # start backends + seed graph, print health
#   ./scripts/dev-stack.sh --front  # also start the Prophet Studio + client-vue dev servers
#   ./scripts/dev-stack.sh --stop   # stop everything this script started
#
# Ports:  agent-machine 8080 · hellgraph-service 8090 · owl-reasoner 8081 ·
#         entity-resolution 8082 · lattice-studio 8083 · dashboard-bff 8077
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS="$REPO/apps"
NOETICA="${NOETICA_DIR:-$HOME/dev/noetica}"
HOLMES="${HOLMES_DIR:-$HOME/dev/holmes}"
CLIENT_VUE="${CLIENT_VUE_DIR:-$HOME/dev/socioprophet/socioprophet-web/client-vue}"
VENV="$REPO/.dev-venv"
LOGS="$REPO/scripts/.dev-logs"
PIDS="$LOGS/pids"
mkdir -p "$LOGS"

port_in_use() { lsof -tiTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

start() { # name port "command..."  (cwd via subshell in the command)
  local name="$1" port="$2" cmd="$3"
  if port_in_use "$port"; then echo "  ✓ $name already on :$port (left as-is)"; return; fi
  echo "  → starting $name on :$port"
  nohup bash -c "$cmd" >"$LOGS/$name.log" 2>&1 &
  echo "$!" >>"$PIDS"
}

wait_health() { # name url
  for _ in $(seq 1 30); do curl -sf "$2" >/dev/null 2>&1 && { echo "  ✓ $1 healthy"; return; }; sleep 1; done
  echo "  ✗ $1 did NOT come up — see $LOGS/$1.log"
}

if [[ "${1:-}" == "--stop" ]]; then
  [[ -f "$PIDS" ]] && while read -r p; do kill "$p" 2>/dev/null && echo "stopped pid $p"; done <"$PIDS"
  : >"$PIDS"; exit 0
fi

# --- python venv (shared by the FastAPI services) ---------------------------
if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  echo "→ creating python venv at $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    fastapi==0.115.0 uvicorn==0.30.6 httpx==0.27.2 rdflib==7.0.0 owlrl==6.0.2 pyshacl==0.26.0 PyJWT==2.9.0 numpy==2.1.2 spacy==3.8.2
  "$VENV/bin/python" -m spacy download en_core_web_sm 2>/dev/null || true
fi
UVICORN="$VENV/bin/uvicorn"
: >"$PIDS"

echo "Booting SocioProphet dev stack…"

# --- graph + knowledge backends ---------------------------------------------
start agent-machine     8080 "cd '$NOETICA/agent-machine' && NOETICA_AM_PORT=8080 npx tsx server.ts"
start hellgraph-service 8090 "cd '$APPS/hellgraph-service' && PORT=8090 npx tsx src/server.ts"
start owl-reasoner      8081 "cd '$APPS/owl-reasoner'      && '$UVICORN' owl_reasoner.server:app      --app-dir src --host 127.0.0.1 --port 8081"
start entity-resolution 8082 "cd '$APPS/entity-resolution' && '$UVICORN' entity_resolution.server:app --app-dir src --host 127.0.0.1 --port 8082"
start lattice-studio    8083 "cd '$APPS/lattice-studio'    && '$UVICORN' lattice_studio.server:app    --app-dir src --host 127.0.0.1 --port 8083"
start dashboard-bff     8077 "cd '$APPS/dashboard-bff'     && '$UVICORN' main:app                     --host 127.0.0.1 --port 8077"
start algo-engine       8085 "cd '$APPS/algo-engine'       && '$UVICORN' algo_engine.server:app       --app-dir src --host 127.0.0.1 --port 8085"
start ie-engine         8086 "cd '$APPS/ie-engine'         && '$UVICORN' ie_engine.server:app         --app-dir src --host 127.0.0.1 --port 8086"
# holmes — Go claim-verifier (build once with CGO_ENABLED=0 to avoid the macOS LC_UUID dyld issue)
[ -x "$HOLMES/bin/holmes" ] || ( cd "$HOLMES" && CGO_ENABLED=0 go build -o bin/holmes ./cmd/holmes 2>/dev/null ) || true
start holmes            8091 "cd '$HOLMES' && HOLMES_HELLGRAPH=http://127.0.0.1:8090 PORT=8091 ./bin/holmes serve"
# synapseiq-bridge — language intelligence (normalization + KKO type classification) over its own tsx
start synapse-bridge    8092 "cd '${SYNAPSEIQ_DIR:-$HOME/dev/synapseiq}' && PORT=8092 ./node_modules/.bin/tsx bridge/server.ts"
# sherlock-engine — Tantivy (Rust, no-JVM) Discovery search. Build once with cargo.
SHERLOCK_ENGINE="${SHERLOCK_DIR:-$HOME/dev/sherlock-search}/engine"
[ -x "$SHERLOCK_ENGINE/target/debug/sherlock-engine" ] || ( cd "$SHERLOCK_ENGINE" && cargo build 2>/dev/null ) || true
start sherlock-engine   8093 "cd '$SHERLOCK_ENGINE' && PORT=8093 ./target/debug/sherlock-engine"

echo "Waiting for health…"
wait_health hellgraph-service http://127.0.0.1:8090/healthz
wait_health owl-reasoner      http://127.0.0.1:8081/healthz
wait_health entity-resolution http://127.0.0.1:8082/healthz
wait_health lattice-studio    http://127.0.0.1:8083/healthz
wait_health dashboard-bff     http://127.0.0.1:8077/health
wait_health algo-engine       http://127.0.0.1:8085/healthz

# --- seed the canonical graph if empty --------------------------------------
if [[ "$(curl -s http://127.0.0.1:8090/api/graph/stats)" == '{"nodes":0,"edges":0}' ]]; then
  echo "→ seeding hellgraph-service from gyg-supply-chain-causal.json"
  "$VENV/bin/python" - "$APPS/hellgraph-service/seeds/gyg-supply-chain-causal.json" <<'PY'
import json, sys, urllib.request
seed = json.load(open(sys.argv[1]))
def post(path, body):
    urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8090'+path,
        data=json.dumps(body).encode(), headers={'Content-Type':'application/json'}, method='POST'), timeout=10)
for n in seed['nodes']: post('/api/graph/node', {'id':n['id'],'labels':n['labels'],'properties':n.get('properties',{})})
for e in seed['edges']: post('/api/graph/edge', {'label':e['label'],'from':e['from'],'to':e['to'],'properties':e.get('properties',{})})
print('   seeded', len(seed['nodes']), 'nodes', len(seed['edges']), 'edges')
PY
fi

# --- optional frontends ------------------------------------------------------
if [[ "${1:-}" == "--front" ]]; then
  start prophet-studio 5173 "cd '$APPS/socioprophet-web' && npm run dev"
  start client-vue     5176 "cd '$CLIENT_VUE' && npm run dev -- --port 5176"
fi

echo
echo "Stack up. Graph: $(curl -s http://127.0.0.1:8090/api/graph/stats)"
echo "Prophet Studio → http://localhost:5173/studio   ·   Cockpit → http://localhost:5176"
echo "Logs: $LOGS   ·   Stop: $0 --stop"
