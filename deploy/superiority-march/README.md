# Superiority-march — deployable config-as-code

The competitive gap register ([`global-devsecops-intelligence`](https://github.com/SocioProphet/global-devsecops-intelligence)
`docs/competitive/where-we-stand.md`) named the capabilities we were behind on. This directory
**executes the infrastructure moves as real, deployable artifacts** — what you `kubectl apply` /
GitOps-sync. They are structurally validated in CI (YAML + kube schema); they **activate on a
cluster**. Each answers a ranked gap, and each is done our way: fail-closed, sealed, sovereign, open.

| Move | Directory | Closes | Our open edge |
|------|-----------|--------|---------------|
| #2 observability (keystone) | `observability/` | unblocks canary/chaos/autoscale | OTel fan-out to self-hosted Prometheus/Tempo/Loki; no SaaS APM |
| #3 progressive delivery | `progressive-delivery/` | `progressive-delivery-auto-rollback` (6 ahead) | Argo Rollouts metric analysis + auto-rollback **AND** a fail-closed sealed-verdict gate in the same analysis |
| #5 service mesh | `mesh/` | mesh net-new (readiness diagram) | Istio mTLS STRICT + header routing = the MeshSpace reference pattern, sovereign |
| #9 compliance evidence | `compliance/` | `compliance-certifications` (zero → mapped) | machine-verifiable receipts + SLSA attestations mapped to SOC2/NIST — stronger than a point-in-time cert |

## Status — honest
These are **cluster-gated**: the manifests are real and correct, but end-to-end verification needs a
live cluster (Argo Rollouts, Istio, kube-prometheus-stack). CI validates structure; a cluster
activates behaviour. The code-only moves (#1 MCP surface, #4 attestation, #6/#7 OSV gate) are
already shipped and unit-tested in their own PRs.

## Still ahead (tracked)
- **#8 developer portal + inner-loop dev-environments** — the largest remaining build (a web console
  + Nocalhost-style DevSpace over CapD, agent-driven via the MCP surface). Design in the march doc.
- **#6/#7 remainder** — wire `advisory_check` into the executor precheck; reachability + autonomous
  fix-and-verify loop.
