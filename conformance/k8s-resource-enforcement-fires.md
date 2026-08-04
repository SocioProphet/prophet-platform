# Negative control: prove k8s resource enforcement actually fires

Every `ResourceContract` emitted by `tools/emit_resource_contracts.py` with an enforcing mode
(`terminate` for a memory limit, `throttle` for a CPU limit) references this procedure. The
sourceos-spec `ResourceContract` schema requires it: a contract that claims enforcement must
point at a procedure that demonstrates the enforcement can act. A limit nobody has watched fire
is indistinguishable from no limit.

This exists because the producer emits contracts from OBSERVED cluster state, and observed state
alone cannot prove teeth — 0 OOMKills means either "the limit works and was never breached" or
"the limit does not enforce and nothing has breached it yet." Only driving a breach distinguishes
them. Until this procedure is run for a given workload, that workload's memory verdict is
correctly `INCONCLUSIVE` (teeth unproven), never `PROVED`.

## Memory (`enforcement: terminate` — OOMKill)

```bash
NS=socioprophet; APP=<deployment>
# 1. read the declared limit
kubectl -n "$NS" get deploy "$APP" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}'; echo
# 2. drive a pod in that workload past its limit (a debug container that allocates)
kubectl -n "$NS" exec deploy/"$APP" -- sh -c 'python3 - <<PY
b=[]
while True: b.append(bytearray(50*1024*1024))   # 50 MiB/loop until the cgroup kills us
PY' || true
# 3. assert the kernel OOM-killed the container (enforcement FIRED)
kubectl -n "$NS" get pod -l app.kubernetes.io/name="$APP" \
  -o jsonpath='{.items[*].status.containerStatuses[*].lastState.terminated.reason}'; echo
#    → must contain "OOMKilled". If it does, the memory limit has teeth → PROVED, firedCount>0.
```

Negative half — remove the limit, repeat, confirm NO OOMKill (the allocation grows unbounded
until the node evicts, a different reason). Restore the limit.

## CPU (`enforcement: throttle`)

CPU throttling does not kill; it delays. The `fired` signal is `cpu.stat`'s `nr_throttled` /
`throttled_usec`, which the k8s API does not expose — which is why CPU contracts are emitted
`INCONCLUSIVE` until this is wired:

```bash
# with cAdvisor/Prometheus scraping container_cpu_cfs_throttled_periods_total:
#   rate(container_cpu_cfs_throttled_periods_total{pod=~"<app>.*"}[5m]) > 0  ⇒ throttle fired
# or exec into the pod and read the cgroup directly:
kubectl -n "$NS" exec deploy/"$APP" -- cat /sys/fs/cgroup/cpu.stat | grep -E 'nr_throttled|throttled_usec'
#   nr_throttled climbing under load ⇒ the CPU limit has teeth → PROVED.
```

## Status

**Memory: EXECUTED — PROVED (2026-08-04).** The memory half is no longer a procedure on paper. It
is now a runnable negative control — [`negative-controls/memory-enforcement/`](negative-controls/memory-enforcement/)
(`run.sh` + `oom-canary.yaml`) — and it was run against the prophet-platform GKE cluster: an
isolated `oom-canary` deployment (64Mi limit) was driven past its limit, the kernel OOM-killed it,
and the producer emitted the loop's **first PROVED** verdict —
`oom-canary-memory: terminate, fired 1×, peak 58Mi < limit 64Mi → PROVED` ("the control has
teeth"). Captured evidence: [`evidence-2026-08-04-PROVED.json`](negative-controls/memory-enforcement/evidence-2026-08-04-PROVED.json).
The canary is torn down after each run — it is a test fixture, never a standing workload.

This proves the cluster's cgroup memory enforcement fires, and that the producer/verdict algebra
can actually reach `PROVED` on real data — not only `INCONCLUSIVE`. Real first-party workloads
stay `INCONCLUSIVE` until each is itself run through the procedure (driving a breach on a live
service is disruptive, so it is done deliberately, per workload), but the mechanism is now proven.

**CPU: still procedure-only.** The throttle counter is not exposed by the k8s API (see the CPU
section above); CPU verdicts remain `INCONCLUSIVE` until the cAdvisor/Prometheus signal is wired
(tracked as a separate backlog item).
