variable "region" {
  type    = string
  default = "us-east-1"
}
variable "cluster_name" {
  type    = string
  default = "prophet-platform"
}
variable "gpu_max_nodes" {
  type    = number
  default = 2
}
variable "gitops_repo_url" {
  type    = string
  default = "https://github.com/SocioProphet/prophet-platform"
}
variable "gitops_revision" {
  type    = string
  default = "main"
}
variable "gitops_path" {
  type    = string
  default = "deploy/argocd"
}
