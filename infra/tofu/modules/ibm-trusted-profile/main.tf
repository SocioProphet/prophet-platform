# IBM IAM Trusted Profile — GitHub Actions OIDC federation.
# IBM's equivalent of AWS IRSA / Azure WIF / GCP WIF.
# GitHub Actions gets a short-lived OIDC token; IBM IAM validates the claim
# and issues a temporary session token. No static API keys in CI.
#
# After apply, store the profile CRN as a GitHub Actions variable (not a secret):
#   IBM_TRUSTED_PROFILE_ID → trusted_profile_id output

resource "ibm_iam_trusted_profile" "github_ci" {
  name        = "github-ci-${var.profile_name_suffix}"
  description = "GitHub Actions OIDC federation — no static API keys"
}

# Claim rule binding GitHub's OIDC token to this profile.
resource "ibm_iam_trusted_profile_claim_rule" "github" {
  profile_id = ibm_iam_trusted_profile.github_ci.id
  type       = "Profile-OIDC"
  realm_name = "https://token.actions.githubusercontent.com"

  conditions {
    claim    = "repository"
    operator = "EQUALS"
    value    = "\"${var.github_repo}\""
  }
}

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
