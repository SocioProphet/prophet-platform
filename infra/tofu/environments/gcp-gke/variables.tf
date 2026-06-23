variable "project_id" {
  type    = string
  default = "socioprophet-platform"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "cluster_name" {
  type    = string
  default = "prophet-platform"
}

variable "gitops_repo_url" {
  type    = string
  default = "https://github.com/SocioProphet/prophet-platform"
}

variable "gitops_revision" {
  type    = string
  default = "main"
}

# Path in the gitops repo Argo CD watches (the ApplicationSets live here).
variable "gitops_path" {
  type    = string
  default = "deploy/argocd"
}
