output "client_id" {
  value       = azurerm_user_assigned_identity.github_ci.client_id
  description = "Store as GitHub Actions variable AZURE_CLIENT_ID (not a secret — it is not a credential)."
}
output "principal_id" {
  value = azurerm_user_assigned_identity.github_ci.principal_id
}
