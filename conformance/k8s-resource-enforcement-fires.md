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

**Procedure only; not yet executed against these workloads.** That is stated plainly and is why
every current verdict is `INCONCLUSIVE`, not `PROVED`: an unrun procedure is honest, whereas
emitting `PROVED` from an unproven limit would be the paper control this whole contract exists to
refuse. Running it (memory first — it is bounded and safe) converts a workload's verdict to
`PROVED` and its `firedCount` to a real count.
