variable "cluster_name" { type = string }
variable "resource_group" { type = string }
variable "location" { type = string }
variable "oidc_issuer_url" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

variable "bindings" {
  type = map(object({
    k8s_namespace    = string
    k8s_sa_name      = string
    scope            = string
    role_definitions = list(string)
  }))
  description = <<-EOT
    Map of binding slug → config.
    k8s_namespace:    Kubernetes namespace
    k8s_sa_name:      Kubernetes ServiceAccount name
    scope:            Azure resource scope for role assignment (e.g. subscription or ACR resource ID)
    role_definitions: Azure built-in role names to assign
  EOT
}
