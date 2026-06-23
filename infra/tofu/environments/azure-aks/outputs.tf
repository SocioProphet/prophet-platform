output "cluster_name" { value = azurerm_kubernetes_cluster.this.name }
output "registry" { value = azurerm_container_registry.this.login_server }
output "get_credentials" {
  value = "az aks get-credentials --resource-group ${azurerm_resource_group.this.name} --name ${azurerm_kubernetes_cluster.this.name}"
}
