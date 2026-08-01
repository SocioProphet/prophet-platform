# Observability Capture & Liveness Strategy v0.1

**Status:** authored 2026-07-31 · drives PR #1161 and the remediation backlog below
**Owner:** Platform / DevSecOps
**Principle:** a control that cannot fail needs a *guaranteed input* — never-fired = suspect.

---

## 1. Why this exists (the verified failure)

On 2026-07-31 a live audit of the `observability` namespace found the stack
**running but not capturing**:

| Signal | State | Evidence |
|---|---|---|
| Metrics (Prometheus) | ✅ working | 12 ServiceMonitors scraping node/kube-state |
| Grafana | ✅ up | dashboards available |
| **Logs (Loki)** | 🔴 **empty 2.5 days** | `loki_ingester_streams_created_total{tenant="fake"} = 0` |
| **Traces (Tempo)** | 🔴 empty | running 2 days, no span source |

We were **paying for Loki/Tempo storage that captured nothing** — and nothing
surfaced the gap. Root causes:

1. **No log shipper** — no promtail/Alloy/vector/fluent DaemonSet, so container
   logs never reached Loki.
2. **Nothing emits OTLP** — no deployment sets `OTEL_EXPORTER_OTLP_ENDPOINT`.
3. **Two conflicting collector configs** — `infra/k8s/otel-collector` is
   "backend-free" (logs/traces → `debug` = discarded); only
   `infra/k8s/observability` wires Loki/Tempo.
4. **No Loki/Tempo ServiceMonitor** — Prometheus wasn't even scraping the
   backends, so the emptiness was invisible to our own monitoring.
5. **DevSecOps Intelligence Workroom not wired** — the ops-intelligence layer
   (`devsecops-intelligence-workroom-v0.1.md`, `PROPHET_REAL_TIME_OPS_FABRIC.md`)
   is design-only; it reads no backend.

This is the **observability twin of the silent-wrong code problem**: a control
declared but never proven to fire.

## 2. The invariant

> Every paid data store must continuously prove non-zero ingestion from a
> declared producer, or it is flagged. Silence is failure, not "all quiet."

The enforcing mechanism is a **canary with a guaranteed input**: a heartbeat
producer that always emits, so `ingestion == 0` is *provably* a broken pipeline
rather than a quiet cluster. That converts an invisible gap into a firing alert.

## 3. Shipped (PR #1161)

- **promtail DaemonSet** → ships all container logs to Loki (no app changes).
- **telemetry-canary** → continuous heartbeat log = guaranteed Loki baseline.
- **loki/tempo/promtail ServiceMonitors** → Prometheus scrapes the backends.
- **telemetry-liveness PrometheusRule** → `LokiNotIngestingLogs` (critical),
  `ObservabilityBackendDown`, `TelemetryCanaryMissing`, `TempoNotReceivingSpans`
  (honest TODO until traces land), `PrometheusScrapeTargetDown`.

## 4. Remediation (completes capture)

1. **Traces** — instrument services (`OTEL_EXPORTER_OTLP_ENDPOINT → otel-collector:4317`
   + auto-instrumentation); silences `TempoNotReceivingSpans`.
2. **Reconcile collectors** — retire the inert `infra/k8s/otel-collector`; one
   wired config only.
3. **Wire the DevSecOps Intelligence Workroom** to LogQL (Loki) + PromQL
   (Prometheus) + Tempo — close the "integrated with globaldevsecops" gap.
4. **Route alerts** — the liveness rules → Alertmanager → the PagerDuty/email
   channels defined in `infra/tofu/modules/monitoring`. Alerts that don't page
   are the same silent trap.

## 5. Prevent recurrence (ops-strategy gates)

- **Producer-before-storage CI gate** — fail CI if a manifest provisions a
  telemetry/data backend (Loki/Tempo/bucket) with no declared producer or
  canary. The declared-unenforced principle, enforced.
- **A canary per pipeline** (metrics/logs/traces) — extend the log canary to a
  **full round-trip** (query Loki for its own heartbeat, export
  `telemetry_roundtrip_ok`): proof of storage + queryability, not just receipt.
- **Empty-store SLO in the receipt spine** — every paid store proves non-zero
  ingestion in the same ledger our code proofs live in.
- **Cost-vs-capture waste alarm** — storage growing while ingestion is flat =
  money burning; alert on the divergence.

## 6. Nice-to-haves

- **Capture-health Grafana dashboard** — ingestion rate per pipeline/namespace.
- **Log/trace-based SLOs** (error rate, p95 latency) feeding the workroom.
- **Retention/tiering** — Loki + Tempo → GCS lifecycle; cardinality guardrails.
- **Grafana Alloy** (supersedes promtail) + **Grafana OnCall** for incidents.
- **Onboard new estates day-one** — the mail VM and Matrix Synapse estates must
  emit into this stack from creation, so the empty-store gap never recurs on
  what we just built.

## 7. Rollout order

1. Deploy PR #1161 (capture + liveness) → Loki non-empty in minutes; verify the
   round-trip.
2. Route alerts (§4.4) → the gap can never again be silent.
3. Producer-before-storage CI gate (§5) → the gap can never again be *shipped*.
4. Traces + collector reconciliation (§4.1–4.2).
5. Wire the DevSecOps workroom (§4.3), then SLOs + dashboards (§6).
