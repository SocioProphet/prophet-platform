# Wave 4 — Chaos engineering (game-days)

Resilience verification against the golden path, with **steady-state defined by
the Wave-1 SLOs**. The Chaos Mesh controller installs via
`infra/argocd/chaos-stack.yaml`; the experiments here are **run manually** during
game-days and are deliberately **not synced by any ApplicationSet** — no fault is
ever injected automatically.

## Experiments (`experiments/`)

- **`hellgraph-gameday.example.yaml`** — a Chaos Mesh `Workflow`: check
  steady-state → **kill a HellGraph pod** → wait → re-check. Hypothesis: the
  StatefulSet's RocksDB PVC rebinds, reads recover, and memory-mesh ingestion
  degrades gracefully. (Pairs with [#675](https://github.com/SocioProphet/prophet-platform/pull/675), the durable StatefulSet.)
- **`hellgraph-network-delay.example.yaml`** — inject 200ms±50ms latency for 5m;
  hypothesis: consumers stay within the p99 SLO.

## Running a game-day

```bash
# 1. label the target namespace so Chaos Mesh may inject (enableFilterNamespace):
kubectl label ns socioprophet chaos-mesh.org/inject=enabled
# 2. watch the Wave-1 SLOs (Grafana) — HellGraphDown / HighErrorRatio / p99.
# 3. apply an experiment:
kubectl apply -f experiments/hellgraph-gameday.example.yaml
# 4. observe recovery; remove when done:
kubectl delete -f experiments/hellgraph-gameday.example.yaml
```

## Safety

- Blast radius restricted via `enableFilterNamespace` (only labelled namespaces).
- Experiments are examples, never in an appset — explicit apply required.
- Chart pinned (chaos-mesh 2.7.0).
