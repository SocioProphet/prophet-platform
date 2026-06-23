output "cluster_name" {
  value = module.eks.cluster_name
}
output "registry" {
  value = aws_ecr_repository.images.repository_url
}
output "get_credentials" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}
