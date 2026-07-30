# IBM IAM Trusted Profile.
#
# ⚠️  THIS MODULE DOES NOT FEDERATE GITHUB ACTIONS. IT CANNOT.
#
# It used to claim to be "IBM's equivalent of AWS IRSA / Azure WIF / GCP WIF"
# and carried a claim rule with type = "Profile-OIDC". No such type exists.
# IBM IAM accepts exactly two claim rule types, and neither one can consume a
# GitHub Actions OIDC token:
#
#   Profile-SAML — federated *human* users from a SAML IdP registered in the
#                  account. Requires realm_name naming that registered realm.
#   Profile-CR   — IBM Cloud *compute resources*. cr_type must be one of
#                  VSI, PVS, BMS, IKS_SA, ROKS_SA, CE — every one of which is a
#                  workload running inside IBM Cloud, identified by a compute
#                  resource token it reads from its own instance metadata
#                  service or projected service account file.
#
# A GitHub-hosted runner is neither. It cannot mint a cr_token, so there is no
# value of `type` that makes this work. IBM's own docs enumerate the ways a
# trusted profile can be assumed — federated users, compute resources, service
# IDs, cloud service instances — and external OIDC providers are not among them.
#
# Refs:
#   https://registry.terraform.io/providers/IBM-Cloud/ibm/latest/docs/resources/iam_trusted_profile_claim_rule
#   https://cloud.ibm.com/docs/account?topic=account-create-trusted-profile
#   https://cloud.ibm.com/docs/account?topic=account-trusted-profile-iam-token
#
# The invalid claim rule is therefore removed rather than swapped for one that
# would pass `tofu validate` while federating nothing. CONSEQUENCE: the profile
# below is created but is NOT ASSUMABLE BY CI. The policies attached to it grant
# nothing to anyone until one of these identity bindings is chosen:
#
#   1. Run the job on IBM compute. Move the drift plan to Code Engine (cr_type
#      "CE") or an IKS workload (cr_type "IKS_SA") and reduce GitHub Actions to
#      a trigger. This is the only option that is genuinely keyless, and it is
#      the true analogue of AWS IRSA — note IRSA is *pod* identity, which IBM
#      does support; it is Azure/GCP-style *CI* federation that IBM lacks.
#   2. Service ID + API key held in GitHub secrets. Supported, works today,
#      but reintroduces the long-lived credential this module set out to avoid.
#      Rotation then has to be owned somewhere.
#   3. Service ID + API key in IBM Secrets Manager, fetched at job start. Still
#      needs a bootstrap credential in GitHub, so it narrows the blast radius
#      rather than removing it.
#
# 1 is the recommendation. 2 and 3 should be treated as interim.
#
# Known-broken dependent (outside this module's lane, not fixed here):
#   .github/workflows/infra-drift-detect.yml posts a GitHub OIDC token to
#   grant_type=urn:ibm:params:oauth:grant-type:cr-token. That exchange expects a
#   compute resource token and will reject a GitHub token. That workflow needs
#   reworking alongside whichever option is chosen.

# The IBM provider is the only non-hashicorp/ namespace provider in this repo,
# so the source address must be declared here as well as in the root module —
# otherwise OpenTofu infers "hashicorp/ibm", which does not exist, and init
# fails before it can resolve the real provider. Version stays pinned in the
# root (envs/.../versions.tf) to keep a single constraint.
terraform {
  required_providers {
    ibm = { source = "IBM-Cloud/ibm" }
  }
}

resource "ibm_iam_trusted_profile" "github_ci" {
  name = "github-ci-${var.profile_name_suffix}"
  # Description states the actual state of the profile, not the intent. Anyone
  # reading this in the IBM console should learn that it grants nothing yet.
  description = "NOT FEDERATED — no claim rule. Intended consumer ${var.github_repo}; IBM has no GitHub Actions OIDC path. See infra/tofu/modules/ibm-trusted-profile/main.tf"
}

# NO CLAIM RULE. See the header. `ibm_iam_trusted_profile_claim_rule` cannot
# express "trust GitHub Actions", and a rule that validated but matched nothing
# would be worse than its absence: it would look like federation was configured.

# Policy: read-only viewer on the resource group + IKS cluster.
resource "ibm_iam_trusted_profile_policy" "viewer" {
  profile_id = ibm_iam_trusted_profile.github_ci.id
  roles      = ["Viewer", "Reader"]

  resources {
    service              = "containers-kubernetes"
    resource_instance_id = var.cluster_id
  }
}

# Policy: COS bucket access for Tofu state (HMAC-free; profile-based).
resource "ibm_iam_trusted_profile_policy" "cos_state" {
  profile_id = ibm_iam_trusted_profile.github_ci.id
  roles      = ["Object Writer", "Object Reader", "Content Reader"]

  resources {
    service              = "cloud-object-storage"
    resource_instance_id = var.cos_instance_crn
    resource_type        = "bucket"
    resource             = var.state_bucket_name
  }
}
