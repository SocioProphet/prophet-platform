# Deployments — Helm chart + Argo CD

How estate services become running workloads on the cluster. One reusable Helm
chart, per-service values, deployed by Argo CD ApplicationSets.

```
charts/socioprophet-service/   reusable chart (Deployment+Service+ConfigMap+HPA+Ingress+SA)
deploy/values/<svc>.yaml        per-service overrides (only what differs)
deploy/argocd/                  ApplicationSets that sync the chart+values to the cluster
  platform-services.yaml          core platform apps        → ns: socioprophet
  workspace-services.yaml         prophet-workspace surfaces → ns: workspace
  fogstack/fogstack-appset.yaml   fog runtime, standard+federal → ns: fogstack-<tier>
```

## Why one chart

Across the estate, services share the same shape (a hardened container + a
Service, sometimes config/secrets/HPA/ingress). Rather than a chart per service
or hand-written manifests, every service deploys through
`socioprophet-service` and supplies a small values file. Adding a service is one
values file + one line in an ApplicationSet.

The chart keeps the hardening already used in the `apps/*/kustomize` bases:
`runAsNonRoot`, `runAsUser: 10001`, `readOnlyRootFilesystem`, dropped
capabilities, seccomp `RuntimeDefault`, a writable `/tmp` emptyDir.

## Image promotion (how an update ships)

1. A service repo's CI calls the reusable `build-image` workflow → pushes
   `…/socioprophet/<image>:<sha>` to Artifact Registry and cosign-signs it.
2. The release bumps `image.tag` in `deploy/values/<svc>.yaml` (the commit SHA).
3. Argo CD sees the change and syncs the new revision. The SHA tag is what gets
   promoted — `latest` is never deployed.

Registry: `us-central1-docker.pkg.dev/socioprophet-platform/socioprophet`.

## Relationship to the existing Kustomize bases

`apps/*/kustomize` and `infra/k8s` are the prior Kustomize manifests. This chart
supersedes them for the services listed in `deploy/values`; migrate a service by
adding its values file and removing its bespoke kustomize once Argo is cut over.
Argo CD consumes the Helm source directly, so this stays within the existing
GitOps model — no new tooling.

## Add a service

```sh
cat > deploy/values/my-svc.yaml <<'EOF'
image: { repository: my-svc }
service: { port: 8080, portName: http }
EOF
# add `- { name: my-svc }` to the relevant ApplicationSet generator
helm template my-svc charts/socioprophet-service -f deploy/values/my-svc.yaml | kubectl apply --dry-run=client -f -
```

## fogstack

`fogstack/fogstack-appset.yaml` deploys the fog-tier services into both
`fogstack-standard` and `fogstack-federal` namespaces (mirrors the existing
`infra/argocd/cloudshell-fog-stack-{standard,federal}` split) and stamps each
workload with `socioprophet.ai/compliance-tier`. **Confirm the fog-tier service
membership** in that file — the current list is the plausible fog-edge runtime
set, not a finalized bill of materials.
