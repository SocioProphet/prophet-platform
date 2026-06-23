# aws-eks — EKS substrate (AWS)

Same platform, AWS underneath: EKS cluster (system + scale-to-zero GPU node
group for finetuning/training) + ECR + Argo CD + the identical root app pointing
at `deploy/argocd`. Charts and ApplicationSets unchanged.

## Apply (needs AWS creds: env or profile)
```sh
tofu init && tofu apply
$(tofu output -raw get_credentials)
```
> Validate-clean; not apply-tested (no AWS keys here). Review before applying.
