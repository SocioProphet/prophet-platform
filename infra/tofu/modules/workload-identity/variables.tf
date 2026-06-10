variable "project_id" { type = string }
variable "project_number" { type = string }

variable "bindings" {
  type = map(object({
    sa_name       = string
    k8s_namespace = string
    k8s_sa_name   = string
    roles         = list(string)
  }))
  description = <<-EOT
    Map of WI binding slug → config.
    sa_name: GCP SA name (short, not email)
    k8s_namespace: Kubernetes namespace
    k8s_sa_name: Kubernetes ServiceAccount name
    roles: GCP roles to grant this SA
  EOT
}
