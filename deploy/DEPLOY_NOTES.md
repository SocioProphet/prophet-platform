# Deploy notes — bring-up state (2026-07-04)

## What's captured here (verified live, moved to GitOps)
- Image tags pinned to `:latest` (see per-service values) — the ImagePullBackOff root cause was
  the chart falling back to appVersion `26.11`, which was never pushed. **`:latest` is mutable —
  promote to immutable commit SHAs before any real environment.**
- `TRITRPC_ALLOW_INSECURE_DEV_KEY: "1"` on api + gateway — **DEV ONLY**. For a real env, provision
  a `TRITRPC_KEY_HEX` secret and set this back to `"0"`.
- `enableServiceLinks: false` on osm-map-api — Kubernetes injects `OSM_MAP_API_PORT=tcp://<svc-ip>`
  (legacy docker-link env), which the app `int()`s and crashes. Chart now supports the toggle.

## KNOWN BLOCKER — ArgoCD sync is stuck (not fixed here)
ArgoCD reports every app `Unknown/Degraded` with:
`error calculating structured merge diff: .status.terminatingReplicas: field not declared in schema`
This is a k8s-1.35 Deployment status field the installed ArgoCD's schema doesn't know, so it cannot
compute a diff and **will not sync anything** — which is why today's fixes had to be applied with
`kubectl set image`/`set env` directly rather than via GitOps.

Fix options (need a live cluster to verify — deliberately NOT shipped unverified):
1. Upgrade ArgoCD to a build that knows `terminatingReplicas` (preferred).
2. Set `ServerSideDiff=false` (annotation `argocd.argoproj.io/compare-options: ServerSideDiff=false`)
   on the appset-generated Applications.
3. `resource.customizations.ignoreDifferences` in argocd-cm for apps/Deployment `.status`.

Until this is fixed, GitOps sync is inert and changes must be applied imperatively.

## Redeploy from clean
`tofu apply` (environments/gcp-gke) recreates the cluster; the images are in GAR; ArgoCD then needs
the sync fix above before it converges the workloads.
