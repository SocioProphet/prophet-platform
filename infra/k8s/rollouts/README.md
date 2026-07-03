# Wave 2 — progressive delivery (canary / A-B) + mesh

Cashes in Wave 1: metric-gated **canary** deploys via Argo Rollouts, and the
**Cilium** mesh (mTLS, L7 policy, Gateway API, Hubble).

## Progressive delivery (`infra/k8s/rollouts`)

- **`analysistemplate-slo.yaml`** (`slo-gate`) — the canary gate. At each step
  Rollouts queries Prometheus for the Wave-1 recording rules
  (`job:request_error_ratio:rate5m`, `job:request_latency_p99:5m`) and **aborts**
  the rollout if 5xx ratio ≥ 5% or p99 ≥ 1.5s. Promotion is metric-gated, not
  time-based.
- **`rollout-hellgraph-service.example.yaml`** — the adoption pattern: canary
  10% → analysis → 50% → analysis → 100%. Kept as an example (a `Rollout`
  supersedes the `Deployment`); copy into a service overlay to adopt.
- **A-B for models/brains**: point a second `AnalysisTemplate` at an eval-score
  metric and the same machinery gates a brain/model canary on quality, not just
  latency — the estate's differentiated use of progressive delivery.

## Mesh (`infra/k8s/mesh`)

- **`cilium-networkpolicy.yaml`** — zero-trust for the graph spine (HellGraph
  reachable only from same-namespace consumers + the Prometheus scraper).
- **`gateway.yaml`** — Gateway API `Gateway` + `HTTPRoute` (served by Cilium),
  the substrate for **traffic-shaped** canaries (Rollouts drives HTTPRoute
  weights instead of replica counts).

## Install (`infra/argocd/progressive-delivery.yaml`)

Sync-wave ordered: `cilium` (-3, CNI) + `argo-rollouts` (-2, controller/CRDs) →
`progressive-delivery-base` (0, the AnalysisTemplate).

## Caveats (need a live cluster)

- **Cilium is the CNI** — install at bootstrap on self-managed/edge (k3s). On
  **GKE Autopilot** the dataplane is already Cilium (Dataplane V2): do **not**
  install the cilium chart there; enable NetworkPolicy + Gateway API via GKE and
  apply `infra/k8s/mesh/base` only.
- Chart versions pinned (cilium 1.16.5, argo-rollouts 2.37.7) — bump deliberately.
- The Rollout example image needs a pinned digest (via `gitops_promote_image.py`).
