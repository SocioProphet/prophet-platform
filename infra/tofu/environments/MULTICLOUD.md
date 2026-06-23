# Multi-cloud substrates

The platform runs on **any** cloud's managed Kubernetes. Only the *substrate*
(cluster + container registry + Argo CD bootstrap) is cloud-specific — the app
layer (`charts/socioprophet-service` + `deploy/argocd` ApplicationSets) is
identical everywhere and never changes per cloud.

```
            app layer (cloud-neutral, one copy)
   charts/socioprophet-service + deploy/values + deploy/argocd
                          │
        ┌─────────┬───────┴───────┬──────────┐
     gcp-gke   azure-aks       aws-eks    ibm-iks      ← swap the substrate only
      (GKE)     (AKS)           (EKS)      (IKS)
```

Each substrate env stands up: a managed cluster + a container registry + Argo CD
+ the **same** root app-of-apps pointing at `deploy/argocd`. Argo then syncs the
identical ApplicationSets onto whichever cloud you're on.

## Substrate parity

| Concern | gcp-gke | azure-aks | aws-eks | ibm-iks |
|---|---|---|---|---|
| Managed k8s | GKE Autopilot | AKS | EKS | IKS (VPC) |
| Registry | Artifact Registry | ACR | ECR | Container Registry |
| GPU (train/finetune) | Autopilot GPU pods | `Standard_NC4as_T4_v3` pool 0→N | `g4dn.xlarge` group 0→N | `gx2-8x64x1v100` pool |
| Argo CD + root app | ✅ identical | ✅ identical | ✅ identical | ✅ identical |
| Status | **applied live ✓** | validate-clean | validate-clean | validate-clean |

Only `gcp-gke` has been applied for real (the others need each cloud's
credentials). All four `tofu validate` clean. GPU pools scale to zero so they
cost nothing until a training/finetuning job requests `nvidia.com/gpu`.

## Add a cloud
Copy the closest env, swap the cluster + registry resources for the new
provider, keep `argocd.tf` (only the provider auth block differs), point
`gitops_path` at `deploy/argocd`. The app layer needs no changes.

## Apply any substrate
```sh
cd infra/tofu/environments/<env>
tofu init && tofu apply
$(tofu output -raw get_credentials)   # point kubectl at the new cluster
```
