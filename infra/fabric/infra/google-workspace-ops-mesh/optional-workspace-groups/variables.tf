variable "google_workspace_customer_id" {
  description = "Google Workspace customer ID. Required for this optional root."
  type        = string
}

variable "google_workspace_impersonated_user_email" {
  description = "Workspace admin user email for delegated provider operations."
  type        = string
}

variable "google_workspace_credentials_file" {
  description = "Path to a local service-account credentials file. Do not commit credentials."
  type        = string
  default     = ""
}

variable "google_workspace_oauth_scopes" {
  description = "OAuth scopes for Workspace group operations."
  type        = list(string)
  default = [
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.group.member"
  ]
}

variable "workspace_groups" {
  description = "Workspace group definitions for the operations mesh."
  type = map(object({
    email       = string
    name        = string
    description = string
    members     = optional(list(string), [])
  }))
  default = {}
}
