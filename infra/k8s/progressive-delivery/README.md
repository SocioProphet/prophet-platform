# Progressive delivery — SLO-gated canary (the observability keystone's payload)

Wires **Argo Rollouts** to the SLOs the observability stack already publishes, so a canary is
promoted only if it holds the error-ratio and p99-latency budgets — and aborts automatically
if it doesn't. This is the keystone that unblocks the three net-new delivery boxes (canary,
chaos verification, metric-driven autoscale): each needs real metrics gating real promotions.

## What's here
- `analysistemplate-slo-gate.yaml` — queries `job:request_error_ratio:rate5m` and
  `job:request_latency_p99:5m` (from `observability/base/prometheusrule-slos.yaml`, where they
  are labelled *"the canary gate metric"*). Fail-closed: a single breach aborts.
- `rollout-reference.yaml` — a canary strategy that runs the gate at each weight step. Copy the
  shape per service, point `service-job` at that service's Prometheus `job` label.

## The anti-theater gate
`tools/validate_analysis_metrics.py` (CI: `progressive-delivery.yml`) fails the build if a
canary AnalysisTemplate queries a recording rule that **isn't defined** (a phantom metric returns
no data → Argo never fails it → every bad deploy silently promotes) or declares **no failure
condition** (a gate that can't fail is not a gate).

## Prerequisites
The `argo-rollouts` controller and the observability stack (kube-prometheus-stack + the SLO
recording rules) must be installed. The Prometheus address in the template targets
`kube-prometheus-stack-prometheus.observability.svc.cluster.local:9090`.
