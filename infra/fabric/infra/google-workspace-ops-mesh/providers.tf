provider "google" {
  project = var.google_project_id != "" ? var.google_project_id : null
}

provider "googleworkspace" {
  customer_id                 = var.google_workspace_customer_id != "" ? var.google_workspace_customer_id : null
  impersonated_user_email    = var.google_workspace_impersonated_user_email != "" ? var.google_workspace_impersonated_user_email : null
  credentials                = var.google_workspace_credentials_file != "" ? file(var.google_workspace_credentials_file) : null
  oauth_scopes               = var.google_workspace_oauth_scopes
}
