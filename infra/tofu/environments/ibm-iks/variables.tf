variable "region" {
  type    = string
  default = "us-south"
}
variable "zone" {
  type    = string
  default = "us-south-1"
}
variable "resource_group" {
  type    = string
  default = "Default"
}
variable "cluster_name" {
  type    = string
  default = "prophet-platform"
}
variable "kube_version" {
  type    = string
  default = "1.30"
}
variable "gpu_flavor" {
  type    = string
  default = "gx2-8x64x1v100"
}
variable "registry_namespace" {
  type    = string
  default = "socioprophet"
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
