# GitHub Actions OIDC federation for GCP — no static service account keys in CI.
# Creates a Workload Identity Pool + GitHub provider + service account that
# GitHub Actions workflows impersonate via short-lived OIDC tokens.
#
# After apply, store the two outputs as GitHub Actions *variables* (not secrets):
#   GCP_WIF_PROVIDER  → wif_provider output
#   GCP_TOFU_SA       → sa_email output

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "OIDC federation for CI — no static SA keys"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"
  description                        = "Maps GitHub OIDC tokens; subject scoped to repo"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "github_ci" {
  project      = var.project_id
  account_id   = "github-ci-tofu"
  display_name = "GitHub CI OpenTofu"
  description  = "Assumed by GitHub Actions via WIF — no key files"
}

resource "google_service_account_iam_member" "github_ci_wi" {
  service_account_id = google_service_account.github_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Read-only GCP access for drift-detection plan runs.
resource "google_project_iam_member" "github_ci_viewer" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
    "roles/resourcemanager.organizationViewer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.github_ci.email}"
}

# State bucket read/write for tofu init + plan.
resource "google_storage_bucket_iam_member" "github_ci_state" {
  bucket = var.state_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.github_ci.email}"
}
