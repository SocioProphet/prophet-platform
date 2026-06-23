# Azure AKS substrate — the cloud-specific half of the platform. The app layer
# (charts/ + deploy/argocd) is identical to every other cloud; only this cluster
# + registry differ. Mirrors infra/tofu/environments/gcp-gke.

resource "azurerm_resource_group" "this" {
  name     = var.resource_group
  location = var.location
}

# Container registry (the AKS equivalent of GAR).
resource "azurerm_container_registry" "this" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "Standard"
  admin_enabled       = false
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  dns_prefix          = var.cluster_name

  default_node_pool {
    name       = "system"
    node_count = 2
    vm_size    = "Standard_D2s_v5"
  }

  identity {
    type = "SystemAssigned"
  }
}

# GPU pool for finetuning / model training. Scales 0→N so it costs nothing idle;
# workloads request it via the nvidia.com/gpu taint toleration.
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = "Standard_NC4as_T4_v3"
  auto_scaling_enabled  = true
  node_count            = 0
  min_count             = 0
  max_count             = var.gpu_max_nodes
  node_taints           = ["nvidia.com/gpu=present:NoSchedule"]
}

# Let the cluster pull images from ACR.
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}
