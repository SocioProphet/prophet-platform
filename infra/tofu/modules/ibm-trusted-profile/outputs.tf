output "trusted_profile_id" {
  value       = ibm_iam_trusted_profile.github_ci.id
  description = "Set as GitHub Actions variable IBM_TRUSTED_PROFILE_ID (not a secret)."
}
output "trusted_profile_crn" {
  value = ibm_iam_trusted_profile.github_ci.crn
}
