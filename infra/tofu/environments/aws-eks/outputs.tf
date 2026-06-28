output "cluster_name" {
  value = module.eks.cluster_name
}
output "registry" {
  value = aws_ecr_repository.images.repository_url
}
output "get_credentials" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}
output "irsa_role_arns" {
  value       = module.irsa.role_arns
  description = "Annotate k8s ServiceAccounts with eks.amazonaws.com/role-arn=<value> to use IRSA."
}
