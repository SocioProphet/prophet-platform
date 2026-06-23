# SocioProphet Helm charts

Reusable charts for deploying estate services to any Kubernetes cluster.
Published two ways by `.github/workflows/helm-release.yml`.

## Install

### Public chart repo (no cloud auth)
```sh
helm repo add socioprophet https://socioprophet.github.io/prophet-platform
helm repo update
helm install my-api socioprophet/socioprophet-service \
  --set image.repository=socioprophet-api --set service.port=9000
```

### OCI (Artifact Registry)
```sh
helm pull oci://us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/charts/socioprophet-service --version 0.1.0
# or install directly
helm install my-api \
  oci://us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/charts/socioprophet-service \
  --version 0.1.0 -f my-values.yaml
```

## Charts

| Chart | Purpose |
|-------|---------|
| `socioprophet-service` | Generic estate service: Deployment + Service (+ ConfigMap/HPA/Ingress/SA), hardened. Drives every service via `deploy/values/<svc>.yaml`. |

## Publishing

Bump the chart `version` in its `Chart.yaml` and merge to `main` — `helm-release`
packages it, cuts a GitHub Release, updates the Pages `index.yaml`, and pushes
the OCI artifact to Artifact Registry.

> One-time: enable GitHub Pages (Settings → Pages → branch `gh-pages`) after the
> first `helm-release` run creates that branch, so the `helm repo add` URL serves.
