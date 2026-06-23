# gcp-gke — GKE Autopilot + Argo CD bootstrap

Stands up the Lane C runtime: a GKE Autopilot cluster, the `socioprophet`
Artifact Registry, Argo CD, and a root app-of-apps that makes Argo sync the
ApplicationSets in `deploy/argocd/` (platform-services, workspace-services,
fogstack). After apply, pushing image SHAs into the chart values is all it takes
to ship.

## What it creates
- `google_container_cluster` — Autopilot, REGULAR channel, deletion-protected, Workload Identity on.
- `google_artifact_registry_repository.socioprophet` — the image registry the `build-image` workflow pushes to.
- `helm_release.argocd` — Argo CD in the `argocd` namespace.
- root `Application` — points Argo at `deploy/argocd` (recurse) so the ApplicationSets self-apply.

## Apply (needs an operator with project owner/editor + container.admin)
```sh
cd infra/tofu/environments/gcp-gke
# first run: comment out the gcs backend in versions.tf, or create the state bucket first
tofu init
tofu plan      # also runs in CI via .github/workflows/tofu-plan.yml
tofu apply
$(tofu output -raw get_credentials)        # point kubectl at the cluster
kubectl -n argocd get applications          # platform-services / workspace-services / fog-*
```

## Dependencies / order
1. Needs `deploy/argocd/*` (PR #657) merged to `main` so the root app finds the ApplicationSets.
2. Grant the CI service account `roles/artifactregistry.writer` on the repo (the `build-image` push identity) — or let this env own that binding (add a `google_artifact_registry_repository_iam_member`).
3. This is the cloud-provisioning step that requires your authorization to `apply`; the code is reviewable/plannable without it.

## Notes
- Autopilot chosen for least ops; switch `enable_autopilot=false` + add node pools for Standard if you need GPUs/daemonsets the fog tier requires.
- State: GCS backend `prophet-tofu-state-socioprophet` (create the bucket once, or run local for the first apply then migrate).
