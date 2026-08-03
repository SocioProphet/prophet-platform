#!/usr/bin/env bash
#
# ephemeral-apply-assert.sh — the effect-canary body for the L1 ephemeral real-apply preflight
# (.github/workflows/ephemeral-apply-preflight.yml). It renders ONE overlay, applies it to a
# throwaway namespace on a hermetic kind cluster, and asserts the CREATE / SPEC-time failure class
# from the 2026-08-02 wave-deploy incident does NOT occur. It lives here, not trapped in YAML, so it
# is invocable and testable on its own (`bash -n` clean; `bash … <overlay> <ns>` locally against a
# kind cluster).
#
# VERDICT:
#   FAIL (exit 1) if a namespace Event has reason `FailedCreate`, or a Rollout/Deployment reports
#     `InvalidSpec` — the SA-not-found / AnalysisTemplate-not-found failure class.
#   PASS (exit 0) as soon as a pod object is CREATED and SCHEDULED (reaches Pending/ContainerCreating
#     with a node assigned). That proves the SA / ConfigMap / PVC / AnalysisTemplate references all
#     resolved. We deliberately do NOT wait for Ready: the real GAR image cannot pull inside kind, so
#     ImagePullBackOff is EXPECTED and is NOT a gate failure — we gate on create/spec signals only.
#   TIMEOUT with neither signal -> exit 1 (fail-closed: an apply that never schedules a pod and never
#     names a failure is not a pass).
#
# The overlay's baked namespace is rewritten onto every rendered object so each wave lands in its own
# throwaway namespace, isolated on the ephemeral cluster.
#
# Env seams (defaults are the CI values):
#   APPLY_ASSERT_TIMEOUT   overall poll budget in seconds   (default 150)
#   APPLY_ASSERT_POLL      seconds between polls             (default 5)
set -euo pipefail

OVERLAY="${1:?usage: ephemeral-apply-assert.sh <overlay-dir> <namespace>}"
NS="${2:?usage: ephemeral-apply-assert.sh <overlay-dir> <namespace>}"
TIMEOUT="${APPLY_ASSERT_TIMEOUT:-150}"
POLL="${APPLY_ASSERT_POLL:-5}"

log() { printf '[apply-assert %s] %s\n' "$NS" "$*" >&2; }

kubectl create namespace "$NS" >/dev/null 2>&1 || true

log "rendering $OVERLAY into namespace $NS and applying"
# Rewrite metadata.namespace onto every object so the whole set lands in the throwaway namespace.
# A kustomize render OR apply error is itself a failure (fail-closed).
if ! kubectl kustomize "$OVERLAY" \
      | python3 -c '
import sys, yaml
ns = sys.argv[1]
docs = [d for d in yaml.safe_load_all(sys.stdin) if isinstance(d, dict)]
for d in docs:
    d.setdefault("metadata", {})["namespace"] = ns
sys.stdout.write(yaml.safe_dump_all(docs))
' "$NS" \
      | kubectl apply -n "$NS" -f - ; then
  log "kustomize render or apply FAILED — fail-closed"
  exit 1
fi

# Return 0 and print a reason when a create/spec-time failure is observed in the namespace.
failure_reason() {
  kubectl get events -n "$NS" -o json 2>/dev/null | python3 -c '
import sys, json
data = json.load(sys.stdin)
for it in data.get("items", []):
    if it.get("reason") == "FailedCreate":
        obj = it.get("involvedObject", {})
        print("FailedCreate on %s/%s: %s" % (obj.get("kind"), obj.get("name"), (it.get("message") or "").strip()))
        sys.exit(0)
sys.exit(1)
' && return 0

  kubectl get rollouts.argoproj.io -n "$NS" -o json 2>/dev/null | python3 -c '
import sys, json
data = json.load(sys.stdin)
for it in data.get("items", []):
    st = it.get("status", {})
    name = it.get("metadata", {}).get("name")
    for c in st.get("conditions", []):
        if (c.get("type") == "InvalidSpec" or c.get("reason") == "InvalidSpec") and c.get("status") == "True":
            print("InvalidSpec Rollout/%s: %s" % (name, (c.get("message") or "").strip()))
            sys.exit(0)
    if st.get("phase") == "Degraded" and "InvalidSpec" in (st.get("message") or ""):
        print("InvalidSpec Rollout/%s: %s" % (name, st.get("message")))
        sys.exit(0)
sys.exit(1)
' && return 0

  kubectl get deployments -n "$NS" -o json 2>/dev/null | python3 -c '
import sys, json
data = json.load(sys.stdin)
for it in data.get("items", []):
    name = it.get("metadata", {}).get("name")
    for c in it.get("status", {}).get("conditions", []):
        if c.get("reason") == "InvalidSpec":
            print("InvalidSpec Deployment/%s: %s" % (name, (c.get("message") or "").strip()))
            sys.exit(0)
sys.exit(1)
' && return 0

  return 1
}

# Return 0 and print a reason once a pod object exists AND has been scheduled (reaches
# Pending/ContainerCreating with a node) — proving the workload's references resolved.
scheduled_pod() {
  kubectl get pods -n "$NS" -o json 2>/dev/null | python3 -c '
import sys, json
data = json.load(sys.stdin)
for it in data.get("items", []):
    spec = it.get("spec", {})
    status = it.get("status", {})
    name = it.get("metadata", {}).get("name")
    phase = status.get("phase")
    scheduled = bool(spec.get("nodeName"))
    if not scheduled:
        for c in status.get("conditions", []):
            if c.get("type") == "PodScheduled" and c.get("status") == "True":
                scheduled = True
    # container statuses present (ContainerCreating/ImagePullBackOff/etc.) also imply the pod was
    # created and admitted — the create/spec class is cleared regardless of pull outcome.
    cs_present = bool(status.get("containerStatuses") or status.get("initContainerStatuses"))
    if scheduled or cs_present or phase in ("Running", "Succeeded"):
        print("pod %s created+scheduled (phase=%s node=%s)" % (name, phase, spec.get("nodeName") or "-"))
        sys.exit(0)
sys.exit(1)
'
}

log "polling up to ${TIMEOUT}s for a create/spec-time failure OR a scheduled pod"
deadline=$(( SECONDS + TIMEOUT ))
while (( SECONDS < deadline )); do
  if reason="$(failure_reason)"; then
    log "DETECTED create/spec-time failure -> FAIL: $reason"
    exit 1
  fi
  if ok="$(scheduled_pod)"; then
    log "PASS: $ok (SA/ConfigMap/PVC/AnalysisTemplate resolved; not waiting for Ready)"
    exit 0
  fi
  sleep "$POLL"
done

log "TIMEOUT after ${TIMEOUT}s: no pod scheduled and no explicit failure — fail-closed. Diagnostics:"
kubectl get events -n "$NS" --sort-by=.lastTimestamp >&2 2>/dev/null || true
kubectl get pods,rollouts.argoproj.io,replicasets,deployments -n "$NS" >&2 2>/dev/null || true
exit 1
