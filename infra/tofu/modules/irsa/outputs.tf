output "role_arns" {
  value       = { for slug, r in aws_iam_role.irsa : slug => r.arn }
  description = "Map of binding slug → IAM role ARN. Annotate k8s ServiceAccounts with these."
}
