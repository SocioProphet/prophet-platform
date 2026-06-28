output "client_ids" {
  value       = { for slug, id in azurerm_user_assigned_identity.wi : slug => id.client_id }
  description = "Map of binding slug → managed identity client ID. Set as azure.workload.identity/client-id annotation on k8s ServiceAccounts."
}

output "principal_ids" {
  value       = { for slug, id in azurerm_user_assigned_identity.wi : slug => id.principal_id }
  description = "Map of binding slug → principal ID."
}
