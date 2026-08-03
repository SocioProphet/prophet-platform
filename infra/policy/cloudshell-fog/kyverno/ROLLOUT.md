# Kyverno signature-enforcement rollout (audit-first, held)

Closes the `sovereign-registry-policy-enforced` gap (git-ops-standards): the estate has a
committed image-signature `ClusterPolicy` (`verify-signed-images.yaml`) but no Kyverno controller,
so signing was **declared, not enforced**. This rollout installs the controller and turns
enforcement on *safely*, in stages — nothing here auto-applies to the cluster.

## Why audit-first + held

Kyverno's image-verification runs as a **validating admission webhook**. In `Enforce` mode any Pod
whose images fail signature verification is **rejected at admission** — a coverage gap (an unsigned
base image, a registry the policy doesn't cover) blocks legitimate deploys cluster-wide. So we
install the controller **held** (no ArgoCD auto-sync) and ship the policy at
`validationFailureAction: Audit` (logs violations, blocks nothing) until the Audit logs are clean.

## Steps

1. **Sync the controller (deliberate).** `deploy/argocd/kyverno.yaml` is a held ArgoCD Application.
   Sync it in the ArgoCD UI/CLI (`argocd app sync kyverno`). Confirm Ready:
   ```
   kubectl -n kyverno get deploy
   kubectl get crd | grep kyverno.io
   ```
2. **Ensure the ClusterPolicy is reconciled.** The `cloudshell-fog` policy stack delivers
   `verify-signed-images.yaml` (Audit). Confirm it admitted once the CRDs exist:
   ```
   kubectl get clusterpolicy cloudshell-verify-signed-images -o jsonpath='{.status.ready}'
   ```
   (This is exactly what `git-ops-standards/estate-sovereign-governance` checks in-cluster; once
   `ready=true` the `sovereign-registry-policy-enforced` finding clears.)
3. **Observe.** Watch Kyverno's policy reports for `fail` results on real workloads:
   ```
   kubectl get policyreport,clusterpolicyreport -A
   ```
   Every failing image is a signing-coverage gap to fix (sign it, or scope the policy), NOT a
   reason to leave enforcement off.
4. **Flip to Enforce (follow-up PR).** When Audit is clean, change
   `verify-signed-images.yaml` `validationFailureAction: Audit -> Enforce` in its own reviewed PR.

## Rollback

Set the policy back to `Audit` (or disable the app) — admission stops blocking immediately. The
controller can be left installed; only the policy's failure action gates workloads.
