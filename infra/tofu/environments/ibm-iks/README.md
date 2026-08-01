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
> Validate-clean as of the PR that added this line — and **not before**. This
> root had never once passed `tofu validate`: it failed at `tofu init` until the
> IBM provider source was declared, and the two errors that unblocking exposed
> had been unreachable the whole time. Not apply-tested (no IBM keys here).
> Confirm flavor names (`bx2.4x16`, `gx2-8x64x1v100`) + kube_version against
> `ibmcloud ks` before applying.

## ⚠️ CI authentication does not work

`module.github_ci` creates an IBM Trusted Profile, but **it has no claim rule and
cannot be assumed by GitHub Actions.** IBM IAM accepts only `Profile-SAML`
(human SSO from a registered SAML realm) and `Profile-CR` (IBM Cloud compute:
`VSI`, `PVS`, `BMS`, `IKS_SA`, `ROKS_SA`, `CE`). A GitHub-hosted runner is
neither, and IBM's IAM identity-provider API has no OIDC type at all — only
`saml`, `appid`, `ldap`. There is no IBM equivalent of GCP/Azure workload
identity federation for CI.

Consequently the `cr-token` exchange in
`.github/workflows/infra-drift-detect.yml` cannot succeed, and applying this
root requires a real credential (`IC_API_KEY`). See the header of
`../../modules/ibm-trusted-profile/main.tf` for the three supported options and
the recommendation.
