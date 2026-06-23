# ibm-iks — IBM Cloud IKS substrate (VPC)

Same platform, IBM Cloud underneath: a VPC IKS cluster (default + scale-capable
GPU pool for finetuning/training) + Container Registry namespace + Argo CD + the
identical root app pointing at `deploy/argocd`. Charts and ApplicationSets
unchanged.

## Apply (needs IBM creds: IC_API_KEY)
```sh
tofu init && tofu apply
$(tofu output -raw get_credentials)
```
> Validate-clean; not apply-tested (no IBM keys here). Confirm flavor names
> (`bx2.4x16`, `gx2-8x64x1v100`) + kube_version against `ibmcloud ks` before applying.
