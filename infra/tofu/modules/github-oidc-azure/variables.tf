variable "cluster_name" { type = string }
variable "resource_group" { type = string }
variable "location" { type = string }
variable "github_repo" {
  type        = string
  description = "GitHub repo in owner/name format (e.g. SocioProphet/prophet-platform)"
}
variable "subscription_scope" {
  type        = string
  description = "Azure subscription resource ID for Reader role assignment"
}
variable "cluster_scope" {
  type        = string
  description = "AKS cluster resource ID for cluster-user role assignment"
}
variable "tags" {
  type    = map(string)
  default = {}
}
