# Progressive delivery (canary / A-B) + mesh

Metric-gated **canary** deploys via Argo Rollouts, and Gateway API traffic-shaped routing
(GKE's native Gateway implementation on this cluster — no separate CNI/mesh chart; see
"Cilium dropped" below).

## Progressive delivery (`infra/k8s/rollouts`)

- **`analysistemplate-slo.yaml`** (`slo-gate`) — the canary gate. At each step
  Rollouts queries Prometheus for the Wave-1 recording rules
  (`job:request_error_ratio:rate5m`, `job:request_latency_p99:5m`) and **aborts**
  the rollout if 5xx ratio ≥ 5% or p99 ≥ 1.5s. Promotion is metric-gated, not
  time-based. **Not wired to any service yet** — see hellgraph-service below.
- **Adoption pattern** (2026-07-31: no longer a standalone example manifest here —
  see `charts/socioprophet-service/templates/rollout.yaml`): set
  `rollout.enabled: true` in a service's `deploy/values/<name>.yaml` and the shared
  chart renders a `Rollout` instead of a `Deployment`, same pod spec either way — one
  deploy path for every service, Rollout or not.
- **hellgraph-service** (`deploy/values/hellgraph-service.yaml`) is the pilot, and is LIVE
  once this merges and ArgoCD syncs: canary 20% → pause 5m → 50% → pause 5m → 100%,
  traffic-shaped via the Gateway API plugin (see Mesh below) — but **metrics-free**, no
  `analysis:` step. hellgraph-service exports no Prometheus metrics today (no `/metrics`,
  confirmed by grep — zero prometheus/otel refs in its source), so `slo-gate` would query an
  empty series, which is not "healthy" and doesn't degrade safely. Adding the gate later is a
  two-line values change once metrics land — see the comment in that file.
- **A-B for models/brains**: point a second `AnalysisTemplate` at an eval-score
  metric and the same machinery gates a brain/model canary on quality, not just
  latency — the estate's differentiated use of progressive delivery. Still just an idea;
  nothing wires this yet.

## Mesh (`infra/k8s/mesh`)

- **`networkpolicy.yaml`** — zero-trust for the graph spine (hellgraph-service reachable
  only from same-namespace consumers + the Prometheus scraper). Native `networking.k8s.io/v1`
  (2026-07-31: was a `CiliumNetworkPolicy` — converted, see below — and its selector/port were
  also wrong, fixed in the same pass: `app: hellgraph`/8850 targeted a different, legacy
  StatefulSet, not this chart-deployed service's `app: hellgraph-service`/8090).
- **`gateway.yaml`** — Gateway API `Gateway` + `HTTPRoute`, the substrate for
  **traffic-shaped** canaries (Rollouts drives HTTPRoute weights instead of replica counts,
  via the `argoproj-labs/gatewayAPI` plugin — Argo Rollouts has no plugin-free native Gateway
  API support, confirmed against the project's docs source at both the pinned controller
  version and the current latest). The `hellgraph-service` HTTPRoute's `backendRefs`
  names/ports must match the canary/stable Service pair the chart renders
  (`rollout-services.yaml`) when a service's `rollout.trafficRouting.enabled` is true — kept
  in sync manually, there's no generator linking the two yet.

### Cilium dropped (2026-07-31)

The original design routed traffic-shaped canaries through a self-managed Cilium install
(`gatewayClassName: cilium`). Live-cluster checks (read-only `kubectl` against
`gke_socioprophet-platform_us-central1_prophet-platform`) found that unnecessary and, for the
NetworkPolicy, broken:
- No `argo-rollouts` namespace, no Rollouts CRDs — the controller had never been installed
  (see "Install" below for why).
- `ciliumnetworkpolicies.cilium.io` is **not** registered — GKE Autopilot's Dataplane V2
  exposes only its own internal Cilium bookkeeping CRDs (ciliumendpoints/ciliumidentities/
  ciliumnodes/ciliumlocalredirectpolicies), never the user-facing CiliumNetworkPolicy CRD a
  `CiliumNetworkPolicy` manifest needs.
- Gateway API CRDs (`gateways`/`httproutes`/`gatewayclasses`/`referencegrants`/`tlsroutes`.
  `gateway.networking.k8s.io`, plus GKE's own `gcpgatewaypolicies.networking.gke.io`) **are**
  already installed — as GKE's native Gateway implementation (`networking.gke.io/gateway`
  controller), confirmed via `kubectl get gatewayclass`
  (`gke-l7-rilb`/`gke-l7-gxlb`/`gke-l7-regional-external-managed`/`gke-l7-global-external-managed`
  all present).

So: `gateway.yaml`'s `gatewayClassName` is `gke-l7-rilb` (regional internal — matches this
Gateway's in-namespace-only intent), no `cilium` Application exists anymore, and
`networkpolicy.yaml` is a plain `NetworkPolicy`. Worth knowing: GKE's Gateway controller
provisions a **real regional internal Google Cloud load balancer** for this HTTPRoute — not a
lightweight in-cluster proxy the way Cilium's own Gateway controller would have been. Fine
for one pilot service; reconsider the cost/behavior tradeoff if more services adopt this.

## Install (`deploy/argocd/progressive-delivery-services.yaml`)

**Moved from `infra/argocd/progressive-delivery.yaml` (2026-07-31)** — that file sat outside
`deploy/argocd`, the only tree the tofu root Application recurses over, so it had **never
reconciled**: confirmed live, no `argo-rollouts` namespace, no Rollouts CRDs at all (only an
unrelated orphaned `experiments.argoproj.io` CRD from a 2026-07-30 partial install attempt).
Same fix class as `deploy/argocd/observability-services.yaml`'s own earlier move.

Sync-wave ordered: `argo-rollouts` (-2, controller/CRDs) → `progressive-delivery-mesh`
(-1, `infra/k8s/mesh/base`) → `progressive-delivery-base` (0, the `AnalysisTemplate`).

Traffic-shaped canaries need the argo-rollouts controller's Gateway API plugin registered
(`controller.trafficRouterPlugins` in the `argo-rollouts` Application's helm values) —
**unverified against a live cluster/the chart's values schema**; confirm once ArgoCD actually
syncs this before relying on it further.

## Caveats (need a live cluster / this PR to actually merge and sync)

- Nothing in this directory is live yet — it's a mergeable diff, not an applied change. Once
  merged: ArgoCD creates the `argo-rollouts` namespace + controller, the `socioprophet-gateway`
  Gateway + `hellgraph-service` HTTPRoute + `NetworkPolicy`, and converts hellgraph-service's
  Helm release from a `Deployment` to a `Rollout` (+ two new canary/stable Services). That
  first conversion is a real cutover (old Deployment pods torn down, new Rollout pods created)
  and — because there's no prior Rollout revision to canary against — happens at 100% directly,
  skipping the weighted steps; the steps first take effect on the *next* spec/image change
  (e.g. the next `gitops-promote`).
- Gateway API CRDs are a separate prerequisite this repo does not install anywhere (GKE ships
  them; self-managed/k3s needs the upstream CRD bundle applied once, out of band, before
  `progressive-delivery-mesh` can sync).
- Chart version pinned (argo-rollouts 2.37.7, controller v1.7.2) — bump deliberately.
- The Rollout's image needs a pinned digest (via `gitops_promote_image.py`), same as every
  other chart-deployed service.
