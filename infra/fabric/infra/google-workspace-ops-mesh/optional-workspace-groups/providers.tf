provider "googleworkspace" {
  customer_id              = var.google_workspace_customer_id
  impersonated_user_email = var.google_workspace_impersonated_user_email
  credentials             = var.google_workspace_credentials_file != "" ? file(var.google_workspace_credentials_file) : null
  oauth_scopes            = var.google_workspace_oauth_scopes
}
