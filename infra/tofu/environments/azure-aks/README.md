# azure-aks — AKS substrate (Azure)

Same platform, Azure underneath. Creates an AKS cluster + ACR + a scale-to-zero
GPU pool (finetuning/training) + Argo CD + the identical root app pointing at
`deploy/argocd`. The Helm charts and ApplicationSets are unchanged from GCP.

## Apply (needs Azure creds: `az login` or ARM_* env)
```sh
tofu init && tofu apply
$(tofu output -raw get_credentials)
```
GPU training pods: tolerate `nvidia.com/gpu=present:NoSchedule` and request
`nvidia.com/gpu` — the pool autoscales 0→N on demand.

> Validate-clean; not apply-tested (no Azure keys here). Review before applying.
