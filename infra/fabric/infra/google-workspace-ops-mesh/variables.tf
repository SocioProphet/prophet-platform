variable "mesh_name" {
  description = "Logical name for this deployment mesh."
  type        = string
  default     = "google-workspace-ops-prototype"
}

variable "google_project_id" {
  description = "Google Cloud project ID used for optional API enablement. Empty keeps project-service resources inert unless enabled with a real project."
  type        = string
  default     = ""
}

variable "enable_google_project_services" {
  description = "When true, Terraform enables listed Google APIs on google_project_id."
  type        = bool
  default     = false
}

variable "google_project_services" {
  description = "Google APIs used by the prototype when project service enablement is explicitly enabled."
  type        = set(string)
  default = [
    "script.googleapis.com",
    "sheets.googleapis.com",
    "calendar-json.googleapis.com",
    "admin.googleapis.com",
    "drive.googleapis.com"
  ]
}

variable "google_workspace_customer_id" {
  description = "Google Workspace customer ID for optional Workspace provider operations."
  type        = string
  default     = ""
}

variable "google_workspace_impersonated_user_email" {
  description = "Workspace admin user email for delegated provider operations."
  type        = string
  default     = ""
}

variable "google_workspace_credentials_file" {
  description = "Path to a local service-account credentials file. Do not commit credentials."
  type        = string
  default     = ""
}

variable "google_workspace_oauth_scopes" {
  description = "OAuth scopes for optional Workspace provider operations."
  type        = list(string)
  default = [
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.group.member"
  ]
}

variable "enable_workspace_groups" {
  description = "When true, Terraform manages Workspace groups defined in workspace_groups."
  type        = bool
  default     = false
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

variable "spreadsheet_id" {
  description = "Prototype ledger Google Sheet ID. Empty means the generated config remains placeholder-only."
  type        = string
  default     = "TODO_GOOGLE_SHEET_ID"
}

variable "apps_script_project_id" {
  description = "Apps Script project ID for generated .clasp.json."
  type        = string
  default     = "TODO_APPS_SCRIPT_PROJECT_ID"
}

variable "cloud_vendor_strategy_calendar_id" {
  description = "Google Calendar ID for SP - Cloud Vendor Strategy."
  type        = string
  default     = "TODO_SP_CLOUD_VENDOR_STRATEGY_CALENDAR_ID"
}

variable "launch_council_calendar_id" {
  description = "Google Calendar ID for SP - Launch Council."
  type        = string
  default     = "TODO_SP_LAUNCH_COUNCIL_CALENDAR_ID"
}

variable "sync_window_days_back" {
  description = "Calendar sync lookback window for generated config."
  type        = number
  default     = 14
}

variable "sync_window_days_forward" {
  description = "Calendar sync forward window for generated config."
  type        = number
  default     = 60
}

variable "prototype_dry_run" {
  description = "Generated Apps Script config dry-run setting. Keep true until handoff gates pass."
  type        = bool
  default     = true
}

variable "generate_local_deployment_files" {
  description = "When true, Terraform writes local generated config files under generated/."
  type        = bool
  default     = true
}

variable "generated_dir" {
  description = "Local generated artifact directory relative to this Terraform root."
  type        = string
  default     = "generated/google-workspace-ops-mesh"
}
