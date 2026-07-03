variable "resource_group" {
  type    = string
  default = "prophet-platform"
}
variable "location" {
  type    = string
  default = "eastus"
}
variable "cluster_name" {
  type    = string
  default = "prophet-platform"
}
variable "acr_name" {
  type    = string
  default = "prophetplatform"
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
variable "subscription_id" {
  type        = string
  description = "Azure subscription ID — used to scope the GitHub CI Reader role"
}
