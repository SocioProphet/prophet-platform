output "role_arn" {
  value       = aws_iam_role.github_ci.arn
  description = "Store as a GitHub Actions variable (not a secret) — set AWS_TOFU_ROLE_ARN=<value> in repo vars."
}
output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
