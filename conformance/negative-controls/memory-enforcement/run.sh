#!/usr/bin/env bash
# Executes the memory-enforcement negative control end to end, against the current kube-context:
#   apply the oom-canary -> wait for a real OOMKill -> run the producer -> assert a PROVED verdict
#   -> save the evidence -> tear the canary down.
#
# This converts the ResourceContract producer's memory verdict from INCONCLUSIVE ("teeth unproven")
# to PROVED ("the cgroup memory limit was observed to fire on this cluster") — with real evidence,
# not a synthetic fixture. Bounded and safe: one small pod in an isolated namespace, always torn
# down (even on failure, via the trap).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
NS=negative-controls

cleanup() { kubectl delete namespace "$NS" --wait=false >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "1/4  applying the oom-canary…"
kubectl apply -f "$HERE/oom-canary.yaml" >/dev/null
kubectl -n "$NS" rollout status deploy/oom-canary --timeout=60s >/dev/null

echo "2/4  waiting for the cgroup memory limit to fire (OOMKilled)…"
for _ in $(seq 1 24); do
  reason=$(kubectl -n "$NS" get pods -l app=oom-canary \
    -o jsonpath='{.items[0].status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null || true)
  [ "$reason" = "OOMKilled" ] && break
  sleep 5
done
[ "${reason:-}" = "OOMKilled" ] || { echo "FAIL: enforcement never fired (no OOMKill) — no teeth?"; exit 1; }
echo "     enforcement FIRED: OOMKilled"

echo "3/4  running the producer (wide window to catch a measured peak)…"
out=$(mktemp -d)
python3 "$ROOT/tools/emit_resource_contracts.py" --namespace "$NS" --samples 6 --interval 8 --out "$out"

echo "4/4  asserting a PROVED memory verdict…"
python3 - "$out" <<'PY'
import json, sys
out = sys.argv[1]
vs = json.load(open(f"{out}/sufficiency-verdicts.json"))
proved = [v for v in vs if v["resource_contract_id"] == "oom-canary-memory" and v["verdict"] == "PROVED"]
if not proved:
    print("FAIL: expected a PROVED memory verdict, got:", [(v["resource_contract_id"], v["verdict"]) for v in vs])
    sys.exit(1)
print("PASS:", json.dumps(proved[0]))
PY
echo "negative control PASSED — memory enforcement has teeth on this cluster."
