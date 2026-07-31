# Wave 2 — progressive delivery (canary / A-B) + mesh

Cashes in Wave 1: metric-gated **canary** deploys via Argo Rollouts, and the
**Cilium** mesh (mTLS, L7 policy, Gateway API, Hubble).

## Progressive delivery (`infra/k8s/rollouts`)

- **`analysistemplate-slo.yaml`** (`slo-gate`) — the canary gate. At each step
  Rollouts queries Prometheus for the Wave-1 recording rules
  (`job:request_error_ratio:rate5m`, `job:request_latency_p99:5m`) and **aborts**
  the rollout if 5xx ratio ≥ 5% or p99 ≥ 1.5s. Promotion is metric-gated, not
  time-based.
- **Adoption pattern** (2026-07-31: no longer a standalone example manifest here —
  see `charts/socioprophet-service/templates/rollout.yaml`): set
  `rollout.enabled: true` in a service's `deploy/values/<name>.yaml` and the shared
  chart renders a `Rollout` (canary 10% → analysis → 50% → analysis → 100%) instead
  of a `Deployment`, same pod spec either way — one deploy path for every service,
  Rollout or not. `deploy/values/hellgraph-service.yaml` carries the pilot config,
  commented out: flip it only after the metrics prerequisite documented there is
  met (hellgraph-service exports no Prometheus metrics today, so `slo-gate` has
  nothing real to query for it yet).
- **A-B for models/brains**: point a second `AnalysisTemplate` at an eval-score
  metric and the same machinery gates a brain/model canary on quality, not just
  latency — the estate's differentiated use of progressive delivery.

## Mesh (`infra/k8s/mesh`)

- **`cilium-networkpolicy.yaml`** — zero-trust for the graph spine (HellGraph
  reachable only from same-namespace consumers + the Prometheus scraper).
- **`gateway.yaml`** — Gateway API `Gateway` + `HTTPRoute` (served by Cilium),
  the substrate for **traffic-shaped** canaries (Rollouts drives HTTPRoute
  weights instead of replica counts). The `hellgraph-service` HTTPRoute's
  `backendRefs` names/ports must match the canary/stable Service pair the chart
  renders (`rollout-services.yaml`) when a service's `rollout.trafficRouting.enabled`
  is true — kept in sync manually, there's no generator linking the two yet.

## Install (`infra/argocd/progressive-delivery.yaml`)

Sync-wave ordered: `cilium` (-3, CNI) + `argo-rollouts` (-2, controller/CRDs) →
`progressive-delivery-mesh` (-1, `infra/k8s/mesh/base` — added 2026-07-31; this
used to be a manual, undocumented-as-code apply step) → `progressive-delivery-base`
(0, the AnalysisTemplate).

Traffic-shaped (not just replica-weighted) canaries additionally need the
argo-rollouts controller's Gateway API plugin registered
(`controller.trafficRouterPlugins` in the `argo-rollouts` Application's helm
values) — added alongside the mesh wiring but **unverified against a live
cluster/the chart's values schema**; confirm before relying on it.

## Caveats (need a live cluster)

- **Cilium is the CNI** — install at bootstrap on self-managed/edge (k3s). On
  **GKE Autopilot** the dataplane is already Cilium (Dataplane V2): skip the
  `cilium` Application there — `progressive-delivery-mesh` (Gateway/HTTPRoute/
  NetworkPolicy only, no CNI) still applies via the same GitOps path either way.
- Gateway API CRDs are a separate prerequisite this repo does not install
  anywhere (GKE ships them; self-managed/k3s needs the upstream CRD bundle
  applied once, out of band, before `progressive-delivery-mesh` can sync).
- Chart versions pinned (cilium 1.16.5, argo-rollouts 2.37.7) — bump deliberately.
- The Rollout's image needs a pinned digest (via `gitops_promote_image.py`), same
  as every other chart-deployed service.
