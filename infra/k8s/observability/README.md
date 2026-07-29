# Observability — Wave 1 (the keystone)

The metric/trace/log backbone that unblocks the rest of the E2E plan: **canary
analysis** (Argo Rollouts reads Prometheus), **chaos steady-state** (Chaos Mesh
verifies SLOs), and **autoscaling** (HPA/KEDA scale on real metrics). Before this
wave the estate had OTLP emitters but no backend to receive them.

## What deploys

Installed as GitOps Argo Applications (`deploy/argocd/observability-services.yaml`
— the tree the tofu root app-of-apps actually watches),
sync-wave-ordered so CRDs exist before the resources that use them:

| Wave | App | Gives |
|---|---|---|
| -3 | `kube-prometheus-stack` | Prometheus (Operator) + Grafana + Alertmanager + the ServiceMonitor/PrometheusRule CRDs |
| -2 | `loki` | logs (OTLP ingest, single-binary) |
| -2 | `tempo` | traces (OTLP ingest) |
| 0 | `observability` (this base) | OTel collector + ServiceMonitors + SLO rules |

## The collector (`base/`)

OTLP in (`:4317` grpc, `:4318` http) → fan-out: **metrics → Prometheus** (scraped
off `:8889` via ServiceMonitor), **traces → Tempo**, **logs → Loki**. The
reasoning-evidence / WorkspaceActionReceipt emitters already speak OTLP, so they
point at `otel-collector.observability.svc:4317`.

## SLOs (`base/prometheusrule-slos.yaml`)

The metric contract downstream waves consume:
- `job:request_error_ratio:rate5m` and `job:request_latency_p99:5m` — the **canary
  gate** metrics (Argo Rollouts AnalysisTemplate queries these).
- `HellGraphDown`, `TargetDown`, `HighErrorRatio` alerts — chaos steady-state.

## Notes / needs a live cluster to confirm

- Chart versions are **pinned** (kube-prometheus-stack 65.5.0, loki 6.18.0, tempo
  1.10.3) — bump deliberately.
- Request-rate rules assume services emit OTel HTTP semconv metrics
  (`http_server_request_duration_seconds_*`) through the collector.
- The `hellgraph` ServiceMonitor assumes metrics on its `http` port at `/metrics`
  (HellGraph ships a prometheus module) — confirm the path on first deploy.
