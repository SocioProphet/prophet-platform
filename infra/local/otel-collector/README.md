# OTel Collector — wiring note

The OpenTelemetry Collector is the trace/metric/log sink for prophet-platform's
OpenInference-conventioned spans. See
`docs/OBSERVABILITY_OTEL_OPENINFERENCE.md` for the span conventions and the
span↔receipt binding.

## Run it locally

```bash
# from infra/local
docker compose -f docker-compose.otel-collector.yml up
# OTLP gRPC :4317 · OTLP HTTP :4318 · Prometheus :8889 · health :13133
```

Compose it with another stack to give services a sink:

```bash
docker compose \
  -f docker-compose.otel-collector.yml \
  -f docker-compose.eval-fabric.yml up
```

## Kubernetes

```bash
kubectl apply -k ../../k8s/otel-collector/overlays/p0-lab
```

## Turn it on in a service

A service starts emitting spans by setting **one env var**:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318   # in-cluster / compose network
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318        # from host to mapped port
OTEL_SERVICE_NAME=eval-fabric-api                        # optional, recommended
```

Then call the tracing seam (`apps/eval-fabric-api/app/tracing.py`):

```python
from app import tracing
from app.receipts import maybe_emit_artifacts

with tracing.reasoning_span("retrieve_evidence", span_kind=tracing.RETRIEVAL) as run_id:
    ...  # work
    maybe_emit_artifacts(..., correlation_id=run_id)  # span ↔ receipt bind by run_id
```

**Inert by default.** If `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, or the
`opentelemetry-sdk` package is not installed, `reasoning_span` is a no-op context
manager that still yields a `correlation_id`. Code behaves identically traced or
untraced. To go live, add to the service's requirements:

```
opentelemetry-sdk
opentelemetry-exporter-otlp
```

## Span ↔ gate relationship

The `approval` span kind reports channel-gate and autonomy-ladder decisions
(`gate.policy_decision_id`, `autonomy.level`); `side_effect` spans should fire
only after an allowed `approval` span. Spans **report** gate decisions — they
never make them, and they never replace the durable receipts
(AutonomyAdmissionReceipt / EvidenceReceipt) the gates emit. Details in
`docs/OBSERVABILITY_OTEL_OPENINFERENCE.md` §5.

## Backends that need real endpoints

`config.yaml` ships backend-free (`debug` exporter). Markers tagged
`NEEDS-REAL-ENDPOINT`:

- **Prometheus** — collector exposes metrics on `:8889`; a Prometheus server must
  scrape it. (Runnable locally, but nothing scrapes it out of the box.)
- **Loki** — `otlphttp/loki` exporter is defined but **disabled** in the logs
  pipeline; point it at a real Loki push endpoint and add it back to the pipeline.
- **Traces** — currently `debug` only; add an `otlphttp/tempo` (or vendor)
  exporter to the traces pipeline for a real trace store.
