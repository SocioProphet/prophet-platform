# cilium-portable overlay

For any environment that is NOT GKE Autopilot (EKS, AKS, self-managed, bare-metal). The
`gcp-gke-autopilot` overlay is what the one live cluster today actually uses — this one exists
so the same workload-facing manifests (HTTPRoute, NetworkPolicy, the Argo Rollouts Gateway API
traffic-shaped canary) don't have to be rewritten per cloud, only re-pointed.

## To adopt this in a new environment

1. Point that environment's ArgoCD app-of-apps at `infra/k8s/mesh/overlays/cilium-portable`
   instead of `overlays/gcp-gke-autopilot` (see how
   `deploy/argocd/progressive-delivery-services.yaml` does this for GKE today).
2. Sync `cilium-application.yaml` in this directory FIRST (or add it to that environment's own
   app-of-apps) — real Cilium must be installed and its Gateway API controller running before
   the `gatewayClassName: cilium` Gateway in this overlay can bind to anything.
3. Everything else (the Argo Rollouts `argoproj-labs/gatewayAPI` plugin, HTTPRoute weight
   shifting, `charts/socioprophet-service`'s `rollout.*` values block) is identical to the GKE
   path — no per-cloud changes needed beyond the GatewayClass + the CNI install.

Not yet exercised against a real AWS/Azure cluster — this is a designed, not yet
operationally-verified, portability path. Verify `kubectl get gatewayclass` shows `cilium`
and the Cilium controller pods are Healthy before trusting a canary through it, same discipline
as was applied to the GKE path.
