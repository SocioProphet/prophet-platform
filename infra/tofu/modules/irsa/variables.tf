variable "cluster_name" { type = string }
variable "oidc_issuer_url" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

variable "bindings" {
  type = map(object({
    k8s_namespace = string
    k8s_sa_name   = string
    policy_arns   = list(string)
  }))
  description = <<-EOT
    Map of binding slug → config.
    k8s_namespace: Kubernetes namespace the SA lives in
    k8s_sa_name:   Kubernetes ServiceAccount name
    policy_arns:   AWS managed or customer policy ARNs to attach
  EOT
}
