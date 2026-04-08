# Observability — Prophet Platform

## Overview

This document covers logging, metrics, and tracing guidance for Prophet Platform services.

---

## Logging

All services write structured logs to stdout (JSON preferred in production).

Key fields to include in every log line:
- `ts` — RFC3339 timestamp
- `level` — info / warn / error
- `service` — e.g. `api`, `gateway`
- `req_id` — per-request correlation ID (audit ID)
- `msg` — human-readable message

**Sensitive data must be redacted** before logging. See [SECURITY-MODEL.md](SECURITY-MODEL.md).

---

## Metrics

Metrics are not yet instrumented. The roadmap includes:
- Request latency (p50 / p95 / p99)
- Error rate by service and RPC method
- CPU and memory usage per workload

See [ROADMAP.md](ROADMAP.md) item 10 (perf budget checks).

---

## Tracing

Distributed tracing is planned. Target: OpenTelemetry with a Jaeger or Tempo backend.
Not yet implemented; tracking in [ROADMAP.md](ROADMAP.md).

---

## Viewing logs in Kubernetes

```bash
# Tail API logs
kubectl logs -n prophet-platform -l app=api --tail=100 -f

# Tail gateway logs
kubectl logs -n prophet-platform -l app=gateway --tail=100 -f
```

---

## Alerting

Not yet configured. When metrics are added, alerts should cover:
- Error rate spike (> 1% for 5 min)
- p99 latency > 500 ms
- Pod crash loop (`CrashLoopBackOff`)
