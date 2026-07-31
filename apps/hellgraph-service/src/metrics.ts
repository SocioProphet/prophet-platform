/**
 * Prometheus metrics for hellgraph-service — closes the gap found while wiring the
 * SLO-gated canary (infra/k8s/rollouts/base/analysistemplate-slo.yaml `slo-gate`):
 * the service had zero metrics instrumentation, so the canary's Prometheus queries
 * always returned empty and the gate could never fire.
 *
 * The recording rules (infra/k8s/observability/base/prometheusrule-slos.yaml)
 * select on the OTel HTTP semantic-convention series name + labels:
 *   http_server_request_duration_seconds_count{http_response_status_code=~"5.."}
 *   http_server_request_duration_seconds_bucket
 * grouped `by (job, le)`. `job` is NOT emitted here — it comes from the Prometheus
 * scrape target (the ServiceMonitor rendered by charts/socioprophet-service when
 * `metrics.enabled: true`, whose default `jobLabel` resolves to the Service's
 * `metadata.name`, i.e. "hellgraph-service" — the exact value the Rollout's
 * AnalysisTemplate arg `service` passes as `job="{{args.service}}"`). This module's
 * only job is to emit the metric NAME and LABELS the recording rules select on —
 * do not rename `http_server_request_duration_seconds` or the `http_response_status_code`
 * label without updating prometheusrule-slos.yaml too, or the gate silently goes
 * back to matching nothing.
 *
 * Deliberately prom-client rather than the full OTel SDK: this service already runs
 * a zero-framework raw `node:http` server (see server.ts's module comment), and
 * prom-client lets us emit the exact semconv-shaped series directly without pulling
 * in the OTel SDK + exporter + collector round-trip for a single histogram.
 */
import type * as http from 'node:http'
import { Registry, Histogram, collectDefaultMetrics } from 'prom-client'

export const registry = new Registry()
collectDefaultMetrics({ register: registry })

// Bucket boundaries match the OTel HTTP server semantic-convention advisory buckets
// (seconds) — see https://opentelemetry.io/docs/specs/semconv/http/http-metrics/.
const HTTP_DURATION_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10]

const httpServerRequestDuration = new Histogram({
  name: 'http_server_request_duration_seconds',
  help: 'Duration of HTTP server requests in seconds (OTel http.server.request.duration semconv shape).',
  labelNames: ['http_request_method', 'http_route', 'http_response_status_code'],
  buckets: HTTP_DURATION_BUCKETS,
  registers: [registry],
})

/**
 * Wrap a raw `http.RequestListener` with request-duration instrumentation. Every
 * route — including /metrics itself — passes through this wrapper before reaching
 * the real handler, because a metrics endpoint that hides its own latency/errors
 * from itself isn't trustworthy.
 *
 * `routeOf` maps a pathname to the `http_route` label. hellgraph-service's routes
 * are all static path strings (params travel in the query string, e.g.
 * `?label=X`), so there is no path-segment cardinality to template away — the
 * pathname itself IS the route. Unmatched/404 paths collapse to a fixed
 * "unmatched" bucket so a scanner probing random paths can't blow up label
 * cardinality on this service.
 */
export function instrumentHttp(
  routeOf: (pathname: string) => string,
  handler: http.RequestListener,
): http.RequestListener {
  return (req, res) => {
    const start = process.hrtime.bigint()
    const method = req.method ?? 'GET'
    let pathname = '/'
    try {
      pathname = new URL(req.url ?? '/', 'http://localhost').pathname
    } catch {
      // malformed req.url — leave pathname as '/', still record the observation
    }
    res.on('finish', () => {
      const seconds = Number(process.hrtime.bigint() - start) / 1e9
      httpServerRequestDuration.observe(
        {
          http_request_method: method,
          http_route: routeOf(pathname),
          http_response_status_code: String(res.statusCode),
        },
        seconds,
      )
    })
    handler(req, res)
  }
}

export function metricsText(): Promise<string> {
  return registry.metrics()
}

export const metricsContentType: string = registry.contentType
