output "wif_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Set as GitHub Actions variable GCP_WIF_PROVIDER (not a secret)."
}
output "sa_email" {
  value       = google_service_account.github_ci.email
  description = "Set as GitHub Actions variable GCP_TOFU_SA (not a secret)."
}
