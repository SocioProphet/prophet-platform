output "cluster_name" { value = azurerm_kubernetes_cluster.this.name }
output "registry" { value = azurerm_container_registry.this.login_server }
output "get_credentials" {
  value = "az aks get-credentials --resource-group ${azurerm_resource_group.this.name} --name ${azurerm_kubernetes_cluster.this.name}"
}
output "wi_client_ids" {
  value       = module.workload_identity.client_ids
  description = "Annotate k8s ServiceAccounts with azure.workload.identity/client-id=<value> to use WIF."
}
output "github_ci_client_id" {
  value       = module.github_ci.client_id
  description = "Set as GitHub Actions variable AZURE_CLIENT_ID (not a secret)."
}
