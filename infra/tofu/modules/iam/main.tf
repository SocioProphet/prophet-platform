# Project-level IAM — persona model per ADR-050
variable "project_id" { type = string }

variable "bindings" {
  type = map(object({
    role    = string
    members = list(string)
  }))
  description = "Map of IAM bindings. Keys are descriptive slugs."
}

variable "audit_config" {
  type = map(list(string))
  default = {
    "allServices" = ["DATA_READ", "DATA_WRITE", "ADMIN_READ"]
  }
  description = "Audit logging config per service. Default: full audit for all services."
}

resource "google_project_iam_binding" "bindings" {
  for_each = var.bindings
  project  = var.project_id
  role     = each.value.role
  members  = each.value.members
}

resource "google_project_iam_audit_config" "audit" {
  for_each = var.audit_config
  project  = var.project_id
  service  = each.key
  dynamic "audit_log_config" {
    for_each = each.value
    content { log_type = audit_log_config.value }
  }
}
